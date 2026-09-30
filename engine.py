"""Motor independente da interface. Coeficientes calculados com Decimal."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import json

APP_VERSION = "PY01"
SCHEMA_VERSION = 1
FAMILIES = {
    "ELUN": "ELU normal", "ELUE": "ELU especial", "ELUC": "ELU construção",
    "ELUX": "ELU excepcional", "ELSR": "ELS rara", "ELSF": "ELS frequente",
    "ELSQP": "ELS quase permanente",
}
RULES = {
    "ELUN": "Σ γG·G + γQ1·Q1 + Σ γQj·ψ0j·Qj",
    "ELUE": "Σ γG·G + γQ1·Qespecial + Σ γQj·ψef,j·Qj",
    "ELUC": "Σ γG·G + γQ1·Qconstrução + Σ γQj·ψef,j·Qj",
    "ELUX": "Σ γG·G + γE·E + Σ γQj·ψef,j·Qj",
    "ELSR": "Σ G + Q1 + Σ ψ1j·Qj",
    "ELSF": "Σ G + ψ1,1·Q1 + Σ ψ2j·Qj",
    "ELSQP": "Σ G + Σ ψ2j·Qj",
}
BANK = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
BANK_HASH = sha256(json.dumps(BANK, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
TYPES = {r["code"]: r for r in BANK["types"]}
PROFILES = {r["code"]: r for r in BANK["profiles"]}
GAMMA = {(r["standard"], r["type"]): r for r in BANK["gamma"]}
PSI = {(r["standard"], r["profile"]): r for r in BANK["psi"]}
ZERO, ONE = Decimal(0), Decimal(1)
MAX_ACTIONS = 200


class InputError(ValueError):
    """Entrada insuficiente, ambígua ou conflitante."""


class GenerationLimit(InputError):
    """Geração interrompida sem retornar resultado parcial."""


def decimal(value, label="fator") -> Decimal:
    if value is None or isinstance(value, bool):
        raise InputError(f"Informe {label}.")
    try:
        d = Decimal(str(value).replace(",", "."))
    except (ValueError, InvalidOperation):
        raise InputError(f"{label}: valor numérico inválido.") from None
    if not d.is_finite():
        raise InputError(f"{label}: valor não finito.")
    return d


def positive_int(value, label, maximum=2_147_483_646):
    d = decimal(value, label)
    if d != d.to_integral_value() or not 1 <= d <= maximum:
        raise InputError(f"{label}: use um inteiro de 1 a {maximum}.")
    return int(d)


def new_project():
    return {
        "schema": SCHEMA_VERSION, "app_version": APP_VERSION, "bank_hash": BANK_HASH,
        "name": "", "standard": None, "families": [], "g_mode": None, "q_mode": None,
        "occupancy_band": None, "temperature_separate": None,
        "effective": {f: None for f in ("ELUE", "ELUC", "ELUX")},
        "effective_reason": "", "prefix": "", "limit": 20000, "visit_limit": 500000,
        "actions": [],
    }


def new_action(case=1):
    return {"case": case, "name": "", "type": None, "profile": None, "origin": "",
            "active": True, "group": None, "compatibility": None, "g_effect": "both",
            "presence": "optional", "primary": True, "families": [],
            "roles": {"ELUE": "companion", "ELUC": "companion"},
            "notes": "", "custom": None}


def fingerprint(project):
    payload = {"project": project, "bank": BANK_HASH, "engine": APP_VERSION}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def example_project():
    p = new_project()
    p.update(name="Exemplo didático — cobertura e quatro ventos", standard="NBR 8800:2024",
             families=["ELUN", "ELSR", "ELSF", "ELSQP"], g_mode="separate", q_mode="separate",
             prefix="EX_")
    for i, name, kind, prof in [
        (1, "Peso próprio", "ACO", None), (2, "Sobrecarga de cobertura", "OUT", "USO3"),
        (3, "Vento +X", "VEN", "VEN"), (4, "Vento -X", "VEN", "VEN"),
        (5, "Vento +Y", "VEN", "VEN"), (6, "Vento -Y", "VEN", "VEN"),
    ]:
        a = new_action(i)
        a.update(name=name, type=kind, profile=prof, origin=f"G{i}" if i == 1 else f"Q{i}",
                 families=p["families"].copy(), notes="Exemplo fictício para teste.")
        if i >= 3:
            a.update(group=1, compatibility="exclusive")
        p["actions"].append(a)
    return p


def grouped_key(project, nature):
    key = "G diretas agrupadas" if nature == "G direta" else "Q agrupadas"
    if project["standard"] == "NBR 14762:2010":
        key += " " + str(project["occupancy_band"])
    return key


def factor_record(project, action):
    """Retorna fatores efetivos, mantendo fonte manual visível e vinculada à norma."""
    standard, kind = project["standard"], action["type"]
    if kind == "CUSTOM":
        c = action.get("custom")
        if not isinstance(c, dict) or c.get("standard") != standard:
            raise InputError("Ação personalizada: confirme os fatores para a norma atual.")
        if not c.get("source", "").strip() or not action.get("notes", "").strip():
            raise InputError("Ação personalizada exige fonte e justificativa.")
        nature = c.get("nature")
        if nature not in ("G direta", "G indireta", "Q", "E"):
            raise InputError("Selecione a natureza da ação personalizada.")
        if nature == "G direta" and project["g_mode"] != "separate" or nature == "Q" and project["q_mode"] != "separate":
            raise InputError("Ação personalizada exige ponderação separada para sua natureza.")
        gv, pv = c.get("gamma"), c.get("psi")
        source_g = source_p = "MANUAL: " + c["source"].strip()
    else:
        row = GAMMA.get((standard, kind))
        if row is None:
            raise InputError("Tipo de ação sem fatores na norma selecionada.")
        nature = row["nature"]
        key = kind
        if nature == "G direta" and project["g_mode"] == "grouped":
            key = grouped_key(project, nature)
        if nature == "Q" and project["q_mode"] == "grouped":
            if not (kind == "TEM" and project["temperature_separate"]):
                key = grouped_key(project, nature)
        row = GAMMA.get((standard, key))
        if row is None:
            raise InputError("Selecione a faixa de uso/ocupação para obter os fatores agrupados.")
        gv, source_g = row["values"], row["source"]
        pv, source_p = None, ""
        if nature == "Q":
            forced = {"VEN": "VEN", "TEM": "TEM"}.get(kind)
            if kind == "TRU" and standard == "NBR 8800:2024":
                forced = "TRU"
            if forced and action.get("profile") != forced:
                raise InputError("O perfil psi deve corresponder ao tipo de ação selecionado.")
            pr = PSI.get((standard, action.get("profile")))
            if pr is None:
                raise InputError("Selecione um perfil psi disponível nesta norma.")
            pv, source_p = pr["values"], pr["source"]
    if not isinstance(gv, list) or len(gv) != 6:
        raise InputError("São necessários seis campos gamma.")
    gs = []
    for j, value in enumerate(gv):
        d = ZERO if nature == "E" and j != 4 else decimal(value, "gamma")
        if not ZERO <= d <= Decimal(100):
            raise InputError("Gamma fora do intervalo admitido pelo aplicativo (0 a 100).")
        gs.append(d)
    ps = (ZERO, ZERO, ZERO)
    if nature == "Q":
        if not isinstance(pv, list) or len(pv) != 3:
            raise InputError("Informe psi0, psi1 e psi2.")
        ps = tuple(decimal(x, "psi") for x in pv)
        if any(not ZERO <= x <= ONE for x in ps):
            raise InputError("Psi deve estar entre 0 e 1.")
    return {"nature": nature, "gamma": tuple(gs), "psi": ps,
            "source_gamma": source_g, "source_psi": source_p, "manual": kind == "CUSTOM"}


@dataclass
class Unit:
    key: str
    actions: list[dict]
    factors: dict

    @property
    def a(self):
        return self.actions[0]


def prepare(project):
    if project.get("bank_hash") != BANK_HASH:
        raise InputError("O projeto usa outra versão do banco normativo. Revise os fatores antes de atualizar o banco.")
    if project.get("standard") not in BANK["standards"]:
        raise InputError("Selecione a norma de referência.")
    families = project.get("families", [])
    if not isinstance(families, list) or not families or len(set(families)) != len(families) or any(f not in FAMILIES for f in families):
        raise InputError("Selecione ao menos uma família de combinação válida.")
    for field_name in ("g_mode", "q_mode"):
        if project.get(field_name) not in ("separate", "grouped"):
            raise InputError("Escolha como ponderar as ações permanentes e variáveis.")
    standard = project["standard"]
    if standard == "NBR 14762:2010" and "grouped" in (project["g_mode"], project["q_mode"]):
        if project.get("occupancy_band") not in (">5", "<=5"):
            raise InputError("Selecione a faixa de uso/ocupação: >5 ou ≤5 kN/m².")
    if project["q_mode"] == "grouped":
        if project.get("temperature_separate") not in (True, False):
            raise InputError("Defina o tratamento da temperatura atmosférica.")
        if standard != "NBR 8800:2024" and project["g_mode"] != "grouped":
            raise InputError("Nesta norma, Q agrupadas exige G diretas agrupadas.")
    for f in ("ELUE", "ELUC", "ELUX"):
        if f in families:
            if project.get("effective", {}).get(f) not in ("psi0", "psi2"):
                raise InputError(f"Selecione psi efetivo para {FAMILIES[f]}.")
            if not project.get("effective_reason", "").strip():
                raise InputError("Justifique a escolha de psi efetivo.")
    positive_int(project.get("limit"), "Limite de combinações", 50000)
    positive_int(project.get("visit_limit"), "Limite de tentativas", 5_000_000)
    prefix = project.get("prefix", "")
    if not isinstance(prefix, str) or len(prefix) > 20 or any(c in prefix for c in "\t\r\n"):
        raise InputError("Prefixo: até 20 caracteres, sem tabulações ou quebras de linha.")
    if prefix.startswith(("=", "+", "-", "@")):
        raise InputError("O prefixo deve começar por uma letra, número ou sublinhado.")
    actions = project.get("actions")
    if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
        raise InputError(f"Cadastre até {MAX_ACTIONS} ações.")
    if any(not isinstance(a, dict) or type(a.get("active")) is not bool for a in actions):
        raise InputError("Cada ação deve declarar Ativa como verdadeiro ou falso.")
    active = [a for a in actions if a.get("active") is True]
    if not active:
        raise InputError("Cadastre ao menos uma ação ativa.")
    units, cases, group_rules = {}, set(), {}
    for a in active:
        cid = positive_int(a.get("case"), "Número do caso Robot")
        if cid in cases:
            raise InputError(f"Número de caso repetido: {cid}.")
        cases.add(cid)
        if not isinstance(a.get("name"), str) or not a["name"].strip():
            raise InputError(f"Caso {cid}: informe o nome.")
        if not isinstance(a.get("origin"), str) or not a["origin"].strip():
            raise InputError(f"Caso {cid}: identifique a origem/ação física.")
        if not isinstance(a.get("notes", ""), str):
            raise InputError(f"Caso {cid}: justificativa inválida.")
        af = a.get("families", [])
        if not isinstance(af, list) or len(af) != len(set(af)) or any(f not in FAMILIES for f in af):
            raise InputError(f"Caso {cid}: famílias inválidas.")
        if type(a.get("primary")) is not bool:
            raise InputError(f"Caso {cid}: defina se pode ser principal.")
        try:
            fr = factor_record(project, a)
        except InputError as exc:
            raise InputError(f"Caso {cid}: {exc}") from exc
        nature = fr["nature"]
        note = a.get("notes", "").strip()
        if nature.startswith("G"):
            if a.get("g_effect") not in ("both", "unfavorable", "favorable"):
                raise InputError(f"Caso {cid}: defina o efeito da permanente.")
            if (a["g_effect"] != "both" or set(families) - set(af)) and not note:
                raise InputError(f"Caso {cid}: justifique a restrição de ponderações ou a exclusão de G.")
            if a.get("group") is not None:
                raise InputError(f"Caso {cid}: use origem física para G; grupo de compatibilidade é para Q/E.")
        elif nature == "Q":
            if a.get("presence") not in ("optional", "required"):
                raise InputError(f"Caso {cid}: defina a presença da variável.")
            if (a["presence"] == "required" or not a["primary"]) and not note:
                raise InputError(f"Caso {cid}: justifique a redução de combinações.")
            for f in ("ELUE", "ELUC"):
                if f in af and a.get("roles", {}).get(f) not in ("primary", "companion"):
                    raise InputError(f"Caso {cid}: defina o papel em {FAMILIES[f]}.")
        elif set(af) - {"ELUX"}:
            raise InputError(f"Caso {cid}: ação excepcional participa apenas de ELU excepcional.")
        group = a.get("group")
        if group is not None:
            group = positive_int(group, "Grupo")
            relation = a.get("compatibility")
            if relation not in ("compatible", "exclusive"):
                raise InputError(f"Caso {cid}: selecione a relação no grupo.")
            if group in group_rules and group_rules[group] != relation:
                raise InputError(f"O grupo {group} mistura compatíveis e incompatíveis.")
            group_rules[group] = relation
        elif a.get("compatibility") is not None:
            raise InputError(f"Caso {cid}: relação sem número de grupo.")
        key = nature + "|" + a["origin"].strip()
        if nature == "G direta" and project["g_mode"] == "grouped":
            key = "G diretas agrupadas"
        if key in units:
            previous = units[key]
            fields = ["families"]
            if nature.startswith("G"):
                fields += ["g_effect"]
            else:
                fields += ["group", "compatibility"]
            if nature == "Q":
                fields += ["presence", "primary", "roles"]
            different = any((set(a[k]) != set(previous.a[k]) if k == "families" else a.get(k) != previous.a.get(k)) for k in fields)
            if different or any(fr[k] != previous.factors[k] for k in ("gamma", "psi")):
                raise InputError(f"Mesma origem/ação com controles ou fatores conflitantes: {key}.")
            previous.actions.append(a)
        else:
            units[key] = Unit(key, [a], fr)
    return list(units.values())


@dataclass
class Combination:
    name: str
    family: str
    cases: tuple[tuple[int, Decimal], ...]
    leaders: list[str] = field(default_factory=list)
    detail: tuple[dict, ...] = ()


@dataclass
class Result:
    combinations: list[Combination]
    signature: str
    counts: dict[str, int]
    duplicates: int
    visits: int


def generate(project, progress=None):
    """Sem estado global de projeto. Excede limite => exceção, nunca saída parcial."""
    project = deepcopy(project)
    units = prepare(project)
    combination_limit = positive_int(project["limit"], "Limite de combinações", 50000)
    visit_limit = positive_int(project["visit_limit"], "Limite de tentativas", 5_000_000)
    rows, seen, counts = [], {}, {f: 0 for f in FAMILIES if f in project["families"]}
    duplicate_count = visits = 0
    selected = [None] * len(units)
    group_in_use = set()

    for family in FAMILIES:
        if family not in counts:
            continue
        elu = family.startswith("ELU")
        gi = 0 if family == "ELUN" else 4 if family == "ELUX" else 2
        effective = project["effective"].get(family)
        eligible = [k for k, unit in enumerate(units) if family in unit.a["families"]]
        if family == "ELSQP":
            leaders = [None]
        else:
            leaders = []
            for k in eligible:
                unit = units[k]
                if family == "ELUX":
                    ok = unit.factors["nature"] == "E"
                elif family in ("ELUE", "ELUC"):
                    ok = unit.factors["nature"] == "Q" and unit.a["roles"][family] == "primary"
                else:
                    ok = unit.factors["nature"] == "Q" and unit.a["primary"]
                if ok:
                    leaders.append(k)
            if not leaders:
                if family in ("ELUE", "ELUC", "ELUX") or any(units[k].factors["nature"] == "Q" for k in eligible):
                    raise InputError(f"{FAMILIES[family]}: não há ação elegível como principal.")
            if family in ("ELUN", "ELSR", "ELSF"):
                leaders.append(None)
        start_count = len(rows)

        def emit(leader):
            nonlocal duplicate_count
            cases, details = [], []
            for unit, choice in zip(units, selected):
                if choice is None:
                    continue
                coefficient, g, reduction, role = choice
                if not coefficient:
                    continue
                for action in unit.actions:
                    case = int(action["case"])
                    cases.append((case, coefficient))
                    action_factors = factor_record(project, action)
                    details.append({"case": case, "name": action["name"], "origin": action["origin"],
                                    "gamma": str(g), "reduction": str(reduction), "coefficient": str(coefficient),
                                    "role": role, "source_gamma": action_factors["source_gamma"],
                                    "source_psi": action_factors["source_psi"], "notes": action.get("notes", "")})
            if not cases:
                return
            cases = tuple(sorted(cases))
            key = family, cases
            leader_name = units[leader].key if leader is not None else "Sem principal"
            if key in seen:
                duplicate_count += 1
                old = rows[seen[key]]
                if leader_name not in old.leaders:
                    old.leaders.append(leader_name)
                return
            if len(rows) >= combination_limit:
                raise GenerationLimit("Limite de combinações atingido. Nenhum conjunto parcial foi liberado. Revise as restrições ou aumente o limite.")
            counts[family] += 1
            name = f"{project['prefix']}{family}_{counts[family]:05d}"
            seen[key] = len(rows)
            rows.append(Combination(name, family, cases, [leader_name], tuple(sorted(details, key=lambda d: d["case"]))))

        def walk(k, leader):
            nonlocal visits
            visits += 1
            if visits > visit_limit:
                raise GenerationLimit("Limite de tentativas atingido. Nenhum conjunto parcial foi liberado.")
            if progress and visits % 4000 == 0:
                progress(len(rows), visits)
            if k == len(units):
                emit(leader)
                return
            unit = units[k]
            a, fr = unit.a, unit.factors
            nature, is_leader = fr["nature"], k == leader
            choices = []
            if family not in a["families"]:
                choices = [(None, False)]
            elif nature.startswith("G"):
                factors = [ONE] if not elu else list(dict.fromkeys(
                    [fr["gamma"][gi]] if a["g_effect"] == "unfavorable" else
                    [fr["gamma"][gi + 1]] if a["g_effect"] == "favorable" else
                    [fr["gamma"][gi], fr["gamma"][gi + 1]]))
                choices = [((g, g, ONE, "Permanente"), True) for g in factors]
            elif nature == "E":
                choices = [((fr["gamma"][4], fr["gamma"][4], ONE, "Excepcional"), True)] if family == "ELUX" and is_leader else [(None, False)]
            elif leader is None and family != "ELSQP":
                choices = [(None, False)] if a["presence"] == "optional" else []
            else:
                p0, p1, p2 = fr["psi"]
                if family == "ELUN":
                    reduction = ONE if is_leader else p0
                elif family in ("ELUE", "ELUC"):
                    reduction = ONE if is_leader else p0 if effective == "psi0" else p2
                elif family == "ELUX":
                    reduction = p0 if effective == "psi0" else p2
                elif family == "ELSR":
                    reduction = ONE if is_leader else p1
                elif family == "ELSF":
                    reduction = p1 if is_leader else p2
                else:
                    reduction = p2
                g = fr["gamma"][gi] if elu else ONE
                coefficient = g * reduction
                if not is_leader and a["presence"] == "optional":
                    choices.append((None, False))
                if is_leader or a["presence"] == "required" or coefficient:
                    role = "Principal" if is_leader else "Quase permanente" if family == "ELSQP" else "Acompanhante"
                    choices.append(((coefficient, g, reduction, role), True))
            for value, present in choices:
                group = a.get("group") if present and a.get("compatibility") == "exclusive" else None
                if group is not None and group in group_in_use:
                    continue
                if group is not None:
                    group_in_use.add(group)
                selected[k] = value
                walk(k + 1, leader)
                if group is not None:
                    group_in_use.remove(group)

        for leader in leaders:
            walk(0, leader)
        if len(rows) == start_count:
            raise InputError(f"{FAMILIES[family]}: nenhuma combinação válida; confira presenças obrigatórias e incompatibilidades.")
    return Result(rows, fingerprint(project), counts, duplicate_count, visits)
