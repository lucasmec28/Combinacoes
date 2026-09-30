"""Arquivos portáveis de projeto e saída tabulada do Robot."""
import csv
import io
import json
from copy import deepcopy
from engine import new_project, new_action, SCHEMA_VERSION, APP_VERSION, InputError, BANK_HASH, BANK, FAMILIES, TYPES, PROFILES, sync_global_families


def dump_project(project):
    return json.dumps(project, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def load_project(data):
    if len(data) > 2_000_000:
        raise InputError('Arquivo de projeto maior que 2 MB.')
    try:
        p = json.loads(data)
        template = new_project()
        if not isinstance(p, dict) or p.get('schema') not in (1, SCHEMA_VERSION):
            raise ValueError('Versão de projeto incompatível.')
        if set(p) != set(template):
            raise ValueError('Estrutura de projeto incompleta ou desconhecida.')
        if p['bank_hash'] != BANK_HASH:
            raise ValueError('Banco normativo diferente. Abra com a versão original e revise antes de migrar.')
        for k in ('name', 'prefix', 'effective_reason', 'app_version', 'bank_hash'):
            if not isinstance(p[k], str):
                raise ValueError(f'Campo inválido: {k}.')
        if not isinstance(p['effective'], dict) or set(p['effective']) != {'ELUE','ELUC','ELUX'}:
            raise ValueError('Estrutura de psi efetivo inválida.')
        if not isinstance(p['families'], list) or any(not isinstance(f,str) for f in p['families']):
            raise ValueError('Famílias inválidas.')
        if not isinstance(p['actions'], list) or len(p['actions']) > 200:
            raise ValueError('Lista de ações inválida (máximo 200).')
        for k in ('limit', 'visit_limit'):
            if type(p[k]) is not int:
                raise ValueError(f'{k} deve ser inteiro.')
        if not 1 <= p['limit'] <= 50000 or not 1 <= p['visit_limit'] <= 5000000:
            raise ValueError('Limites fora do intervalo do aplicativo.')
        choices = {'standard': [None]+BANK['standards'], 'g_mode':[None,'separate','grouped'],
                   'q_mode':[None,'separate','grouped'], 'occupancy_band':[None,'<=5','>5']}
        for k, values in choices.items():
            if p[k] not in values: raise ValueError(f'{k} desconhecido.')
        if p['temperature_separate'] is not None and type(p['temperature_separate']) is not bool:
            raise ValueError('Tratamento de temperatura inválido.')
        if any(v not in (None,'psi0','psi2') for v in p['effective'].values()):
            raise ValueError('Psi efetivo desconhecido.')
        if any(f not in FAMILIES for f in p['families']) or len(set(p['families']))!=len(p['families']):
            raise ValueError('Famílias desconhecidas ou repetidas.')
        for a in p['actions']:
            if not isinstance(a,dict) or set(a) != set(new_action()):
                raise ValueError('Estrutura de ação inválida.')
            if type(a['case']) is not int or type(a['active']) is not bool or type(a['primary']) is not bool:
                raise ValueError('Número de caso ou opções booleanas inválidos.')
            if a['group'] is not None and type(a['group']) is not int:
                raise ValueError('Grupo deve ser inteiro.')
            if not 1<=a['case']<=2147483646 or a['group'] is not None and not 1<=a['group']<=2147483646:
                raise ValueError('Caso ou grupo fora do intervalo.')
            for k in ('name','origin','notes'):
                if not isinstance(a[k],str): raise ValueError(f'{k} inválido.')
            if not isinstance(a['families'],list) or any(not isinstance(f,str) for f in a['families']):
                raise ValueError('Famílias da ação inválidas.')
            if not isinstance(a['roles'],dict) or set(a['roles']) != {'ELUE','ELUC'}:
                raise ValueError('Papéis da ação inválidos.')
            if a['custom'] is not None and not isinstance(a['custom'],dict):
                raise ValueError('Fatores personalizados inválidos.')
            opts={'type':[None,'CUSTOM']+list(TYPES), 'profile':[None]+list(PROFILES),
                  'compatibility':[None,'compatible','exclusive'], 'g_effect':['both','favorable','unfavorable'],
                  'presence':['optional','required']}
            if any(a[k] not in values for k,values in opts.items()):
                raise ValueError('Opção de ação desconhecida.')
            if any(f not in FAMILIES for f in a['families']) or len(set(a['families']))!=len(a['families']):
                raise ValueError('Famílias da ação desconhecidas ou repetidas.')
            if any(v not in ('primary','companion') for v in a['roles'].values()):
                raise ValueError('Papel da ação desconhecido.')
            c=a['custom']
            if c is not None:
                if set(c)!={'standard','nature','gamma','psi','source'} or c['standard'] not in BANK['standards'] or c['nature'] not in ('G direta','G indireta','Q','E') or not isinstance(c['source'],str):
                    raise ValueError('Estrutura de fatores manuais inválida.')
                for k,n in [('gamma',6),('psi',3)]:
                    if not isinstance(c[k],list) or len(c[k])!=n or any(type(v) not in (str,int,float) for v in c[k]):
                        raise ValueError('Quantidade ou tipo de fatores manuais inválidos.')
        # Também rejeita NaN/Infinity, aceitos pelo decodificador JSON padrão.
        dump_project(p)
        p['schema']=SCHEMA_VERSION
        p['app_version']=APP_VERSION
        return sync_global_families(deepcopy(p))
    except (ValueError, TypeError, KeyError) as exc:
        raise InputError(f'Não foi possível abrir: {exc}') from None


def number_text(d, decimal_comma=True):
    s = format(d, 'f').rstrip('0').rstrip('.') if '.' in format(d,'f') else format(d,'f')
    return s.replace('.', ',') if decimal_comma else s


def robot_tsv(combinations, decimal_comma=True):
    rows = [[c.name] + [v for cid,coef in c.cases for v in (str(cid),number_text(coef,decimal_comma))] for c in combinations]
    width = max((len(r) for r in rows),default=0)
    # Retângulo de células, sem cabeçalho e sem coluna automática de numeração.
    return '\r\n'.join('\t'.join(r + ['']*(width-len(r))) for r in rows)


def audit_csv(combinations):
    out=io.StringIO(newline='')
    fields=['combination','family','case','name','origin','gamma','reduction','coefficient','role','source_gamma','source_psi','notes']
    writer=csv.DictWriter(out,fields,delimiter=';')
    writer.writeheader()
    for c in combinations:
        for d in c.detail:
            row=dict(combination=c.name,family=c.family,**d)
            # Arquivo de conferência pode conter texto livre do usuário.
            row={k: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for k,v in row.items()}
            writer.writerow(row)
    return out.getvalue().encode('utf-8-sig')
