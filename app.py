"""Interface Streamlit. Execute: streamlit run app.py"""
from copy import deepcopy
import json
import pandas as pd
import streamlit as st
from engine import (BANK, BANK_HASH, TYPES, PROFILES, GAMMA, PSI, FAMILIES, RULES,
                    InputError, new_project, new_action, example_project, factor_record,
                    generate, fingerprint)
from project_io import dump_project, load_project, robot_tsv, audit_csv

st.set_page_config(page_title='Combinações • Robot', page_icon='🏗️', layout='wide')
st.markdown('''<style>
.block-container {padding-top:2rem;max-width:1450px}
[data-testid="stMetric"] {background:#edf5f5;border-radius:12px;padding:16px}
[data-testid="stSidebar"] {background:#f1f5f9}
h1 {letter-spacing:-.04em} .stCaption {line-height:1.5}
</style>''',unsafe_allow_html=True)
if 'project' not in st.session_state:
    st.session_state.project=new_project()
    st.session_state.revision=0
    st.session_state.edit_revision=0
    st.session_state.edit_index=None


def replace_project(p):
    st.session_state.project=deepcopy(p)
    st.session_state.revision+=1
    st.session_state.edit_revision+=1
    st.session_state.edit_index=None
    st.session_state.pop('result',None)


def pick(label, options, value, key, labels=None, help=None):
    return st.selectbox(label, options, index=options.index(value) if value in options else None,
                        format_func=(lambda x: labels.get(x,x)) if labels else str,
                        placeholder='Selecione…', key=key,help=help)


p=st.session_state.project
rev=st.session_state.revision
with st.sidebar:
    st.markdown('### COMBINAÇÕES / ROBOT')
    st.caption('Estruturas metálicas · ELU + ELS')
    p['name']=st.text_input('Projeto',value=p['name'],key=f'name_{rev}',placeholder='Nome da estrutura')
    p['standard']=pick('Norma de referência',BANK['standards'],p['standard'],f'std_{rev}',
        help='Os fatores são buscados exclusivamente nesta norma. NBR 8800 inclui a errata de 2025.')
    p['families']=st.multiselect('Combinações a gerar',list(FAMILIES),default=p['families'],format_func=FAMILIES.get,key=f'families_{rev}')
    with st.expander('Ponderação e critérios',expanded=p['g_mode'] is None):
        modes={'separate':'Separadamente, por ação','grouped':'Agrupadas conforme a norma'}
        p['g_mode']=pick('Permanentes diretas (γG)',list(modes),p['g_mode'],f'gm_{rev}',modes)
        p['q_mode']=pick('Variáveis (γQ)',list(modes),p['q_mode'],f'qm_{rev}',modes)
        if p['standard']=='NBR 14762:2010' and 'grouped' in (p['g_mode'],p['q_mode']):
            p['occupancy_band']=pick('Uso / ocupação (kN/m²)',['<=5','>5'],p['occupancy_band'],f'occ_{rev}',{'<=5':'Até 5 kN/m²','>5':'Acima de 5 kN/m²'})
        if p['q_mode']=='grouped':
            p['temperature_separate']=pick('Temperatura atmosférica separada?', [True,False],p['temperature_separate'],f'temp_{rev}',{True:'Sim',False:'Não'})
        for f in ('ELUE','ELUC','ELUX'):
            if f in p['families']:
                p['effective'][f]=pick(f'ψ efetivo · {FAMILIES[f]}',['psi0','psi2'],p['effective'][f],f'ef_{f}_{rev}',{'psi0':'ψ0','psi2':'ψ2'})
        if set(p['families']) & {'ELUE','ELUC','ELUX'}:
            p['effective_reason']=st.text_area('Critério / duração que fundamenta ψ efetivo',value=p['effective_reason'],key=f'efreason_{rev}')
        p['prefix']=st.text_input('Prefixo dos nomes',value=p['prefix'],max_chars=20,key=f'prefix_{rev}')
        p['limit']=st.number_input('Máximo de combinações',1,50000,int(p['limit']),step=100,key=f'limit_{rev}')
        p['visit_limit']=st.number_input('Máximo de tentativas',1,5000000,int(p['visit_limit']),step=10000,key=f'visits_{rev}')
    with st.expander('Abrir / salvar projeto'):
        st.caption('Baixe o JSON para guardar suas entradas e reabrir em outro momento. A sessão não é um arquivo salvo.')
        uploaded=st.file_uploader('Projeto salvo (.json)',type=['json'],key=f'upload_{rev}')
        if st.button('Abrir arquivo',disabled=uploaded is None):
            try:
                replace_project(load_project(uploaded.getvalue()))
                st.rerun()
            except InputError as exc: st.error(str(exc))
        st.download_button('Baixar projeto JSON',dump_project(p),'projeto_combinacoes.json','application/json',on_click='ignore')
        st.caption('Abrir um arquivo ou exemplo substitui as entradas da sessão. Baixe o projeto antes, se quiser preservá-lo.')
        if st.button('Carregar exemplo didático'):
            replace_project(example_project());st.rerun()
        if st.button('Novo projeto vazio'):
            replace_project(new_project());st.rerun()

st.title('Combinações prontas para o Robot')
st.caption('Cadastre os casos, defina os critérios e copie a tabela. Fatores e decisões ficam disponíveis para conferência.')
if p['name'].startswith('Exemplo didático'):
    st.info('EXEMPLO FICTÍCIO — os carregamentos e a categoria de uso servem para demonstrar a interface. Substitua-os pelos critérios do seu projeto.')
tab_actions,tab_result,tab_bank,tab_help=st.tabs(['01 · Ações','02 · Gerar e copiar','03 · Fatores e critérios','Como usar'])
with tab_actions:
    left,right=st.columns([1.15,1],gap='large')
    with left:
        st.subheader('Casos de carregamento')
        if p['actions']:
            summary=[{'Ativo':a['active'],'Caso':a['case'],'Nome':a['name'],'Tipo':TYPES.get(a['type'],{}).get('label','Personalizada'),
                      'Origem':a['origin'],'Grupo':str(a['group'] or '—'),'Relação':{'exclusive':'Incompatíveis','compatible':'Compatíveis'}.get(a['compatibility'],'—'),
                      'Famílias':', '.join(a['families'])} for a in p['actions']]
            st.dataframe(pd.DataFrame(summary),hide_index=True,width='stretch')
            selected=st.selectbox('Escolha uma ação para editar',range(len(p['actions'])),format_func=lambda i:f"{p['actions'][i]['case']} · {p['actions'][i]['name']}",key=f'select_{rev}')
            b1,b2,b3=st.columns(3)
            if b1.button('Editar ação'):
                st.session_state.edit_index=selected;st.session_state.edit_revision+=1;st.rerun()
            if b2.button('Duplicar ação'):
                a=deepcopy(p['actions'][selected]);a['case']=max(x['case'] for x in p['actions'])+1
                a['name']+=' (cópia)';a['origin']=f"AÇÃO_{a['case']}";p['actions'].append(a)
                st.session_state.edit_index=len(p['actions'])-1;st.session_state.edit_revision+=1;st.rerun()
            if b3.button('Excluir ação'):
                p['actions'].pop(selected);st.session_state.edit_index=None;st.session_state.edit_revision+=1
                st.session_state.revision+=1;st.rerun()
        else: st.info('Comece pelo cadastro ao lado ou carregue o exemplo no menu lateral.')
        st.caption('Origem = ação física. Casos com a mesma origem são inseparáveis. Grupo = relação entre ações diferentes: em um grupo incompatível, só uma origem entra por combinação.')
    with right:
        idx=st.session_state.edit_index
        editing=idx is not None and idx<len(p['actions'])
        base=deepcopy(p['actions'][idx]) if editing else new_action(max((a['case'] for a in p['actions']),default=0)+1)
        key=f'a_{rev}_{st.session_state.edit_revision}'
        st.subheader('Editar ação' if editing else 'Adicionar ação')
        a=deepcopy(base)
        c1,c2=st.columns([1,2])
        a['case']=c1.number_input('Número do caso no Robot',1,2147483646,int(base['case']),key=key+'case')
        a['name']=c2.text_input('Nome do carregamento',base['name'],key=key+'name')
        available=[code for code in TYPES if (p['standard'],code) in GAMMA]+['CUSTOM']
        a['type']=pick('Tipo de carregamento',available,base['type'],key+'type',{**{k:v['label'] for k,v in TYPES.items()},'CUSTOM':'Personalizada — fatores informados pelo calculista'})
        nature=TYPES.get(a['type'],{}).get('nature')
        if a['type']=='CUSTOM':
            st.warning('Fatores manuais: informe a fonte, vincule à norma selecionada e justifique. Não serão apresentados como valores do banco normativo.')
            custom=base['custom'] or {'nature':None,'gamma':['']*6,'psi':['']*3,'source':''}
            nature=pick('Natureza',['G direta','G indireta','Q','E'],custom.get('nature'),key+'nature')
            gs=[]
            for j,label in enumerate(['γ normal desfavorável / Q','γ normal favorável','γ especial/construção desfavorável / Q','γ especial/construção favorável','γ excepcional desfavorável / Q / E','γ excepcional favorável']):
                if nature=='E' and j!=4 or nature=='Q' and j in (1,3,5):
                    gs.append(0)
                else:
                    value=custom.get('gamma',['']*6)[j]
                    gs.append(st.text_input(label,str(value) if value is not None else '',key=key+f'g{j}'))
            ps=[st.text_input(f'ψ{j}',str(custom.get('psi',['']*3)[j] if custom.get('psi') else ''),key=key+f'p{j}') for j in range(3)] if nature=='Q' else [0,0,0]
            source=st.text_input('Fonte dos fatores manuais',custom.get('source',''),key=key+'source')
            a['custom']={'standard':p['standard'],'nature':nature,'gamma':gs,'psi':ps,'source':source}
        else:a['custom']=None
        if nature=='Q' and a['type']!='CUSTOM':
            profiles=[k for k in PROFILES if (p['standard'],k) in PSI]
            forced={'VEN':'VEN','TEM':'TEM'}.get(a['type'])
            if a['type']=='TRU' and p['standard']=='NBR 8800:2024':forced='TRU'
            a['profile']=forced if forced else pick('Categoria para ψ0 / ψ1 / ψ2',profiles,base['profile'],key+'profile',{k:v['label'] for k,v in PROFILES.items()})
            if forced:st.caption(f"Perfil ψ vinculado: {PROFILES[forced]['label']}")
            if (p['standard'], a['profile']) in PSI:
                profile_row=PSI[(p['standard'],a['profile'])]
                st.caption(f"ψ0 / ψ1 / ψ2: {' / '.join(str(v) for v in profile_row['values'])}. {profile_row.get('note','')}")
        elif nature!='Q':a['profile']=None
        a['origin']=st.text_input('Origem / identificação da ação física',base['origin'],key=key+'origin',placeholder='Ex.: PESO_ESTRUTURA ou VENTO_X_POS',help='Mesma origem une casos que representam uma única ação física. Use origens diferentes para ações independentes.')
        a['active']=st.checkbox('Ação ativa',base['active'],key=key+'active')
        allowed=['ELUX'] if nature=='E' else list(FAMILIES)
        a['families']=st.multiselect('Participa das combinações',allowed,default=[f for f in base['families'] if f in allowed],format_func=FAMILIES.get,key=key+'families',help='Marque explicitamente as famílias aplicáveis a esta ação.')
        if nature and nature.startswith('G'):
            a['group']=None;a['compatibility']=None
            a['g_effect']=pick('Ponderações a considerar',['both','unfavorable','favorable'],base['g_effect'],key+'effect',{'both':'Favorável e desfavorável','unfavorable':'Somente desfavorável','favorable':'Somente favorável'})
            st.caption('A classificação favorável/desfavorável depende do efeito verificado. Restringir exige justificativa e conhecimento dos esforços envolventes.')
        if nature in ('Q','E'):
            group=st.number_input('Grupo de compatibilidade (0 = sem grupo)',0,2147483646,int(base['group'] or 0),key=key+'group')
            a['group']=group or None
            a['compatibility']=pick('Relação dentro do grupo',['compatible','exclusive'],base['compatibility'],key+'relation',{'compatible':'Compatíveis — podem coexistir','exclusive':'Incompatíveis — uma origem por vez'}) if group else None
        if nature=='Q':
            a['presence']=pick('Presença como acompanhante',['optional','required'],base['presence'],key+'presence',{'optional':'Variar presença / ausência','required':'Sempre presente quando aplicável'})
            a['primary']=st.checkbox('Pode ser principal em ELU normal / ELS',base['primary'],key=key+'primary')
            for f in ('ELUE','ELUC'):
                if f in a['families']:
                    a['roles'][f]=pick(f'Papel em {FAMILIES[f]}',['primary','companion'],base['roles'][f],key+f,{'primary':'Ação especial/de construção principal','companion':'Acompanhante'})
        a['notes']=st.text_area('Justificativa / observações',base['notes'],key=key+'notes',placeholder='Fundamente aqui as restrições e os fatores manuais.')
        if st.button('Salvar ação' if editing else 'Adicionar ao cadastro',type='primary'):
            try:
                if not a['name'].strip() or not a['origin'].strip():raise InputError('Preencha nome e origem da ação.')
                if any(x['case']==a['case'] for i,x in enumerate(p['actions']) if not editing or i!=idx):raise InputError('Este número de caso já está cadastrado.')
                if len(p['actions'])>=200 and not editing:raise InputError('Limite de 200 ações.')
                factor_record(p,a)
                if editing:p['actions'][idx]=a
                else:p['actions'].append(a)
                st.session_state.edit_index=None;st.session_state.edit_revision+=1;st.rerun()
            except InputError as exc:st.error(str(exc))
        if editing and st.button('Cancelar edição'):
            st.session_state.edit_index=None;st.session_state.edit_revision+=1;st.rerun()
        st.caption('Alterações do formulário entram no projeto somente ao salvar a ação.')

with tab_result:
    st.subheader('Gerar, conferir e copiar')
    st.caption('A saída usa somente casos numéricos e coeficientes. Os nomes são gerados com o prefixo escolhido e a família de combinação.')
    if st.button('Gerar combinações',type='primary'):
        st.session_state.pop('result',None)
        try:
            with st.spinner('Validando entradas e gerando combinações…'):
                st.session_state.result=generate(p)
        except InputError as exc:st.error(str(exc))
    result=st.session_state.get('result')
    if result and result.signature!=fingerprint(p):
        st.warning('As entradas mudaram após a última geração. Gere novamente para liberar a cópia e os downloads.')
        result=None
    if result:
        m1,m2,m3=st.columns(3)
        m1.metric('Combinações distintas',len(result.combinations));m2.metric('Famílias',len(result.counts));m3.metric('Repetições removidas',result.duplicates)
        st.caption(' · '.join(f'{FAMILIES[f]}: {n}' for f,n in result.counts.items()))
        families=st.multiselect('Famílias a copiar / baixar',list(result.counts),default=list(result.counts),format_func=FAMILIES.get,key='export_families_'+result.signature)
        rows=[c for c in result.combinations if c.family in families]
        decimal_comma=st.radio('Separador decimal',[True,False],format_func=lambda v:'Vírgula (1,25)' if v else 'Ponto (1.25)',horizontal=True)
        text=robot_tsv(rows,decimal_comma)
        st.info('Robot: cole a partir da coluna Nome. A sequência é Nome | Caso | Coeficiente | Caso | Coeficiente… A numeração de Combinações é automática. Confira também a classificação ELU/ELS no Robot: o nome não configura essa classificação.')
        if rows:
            st.caption(f'{len(rows)} linhas selecionadas. Use o ícone de copiar no canto superior direito do bloco. O conteúdo não tem cabeçalho.')
            st.code(text,language=None,height=290,wrap_lines=False)
            d1,d2,d3=st.columns(3)
            d1.download_button('Baixar tabela Robot (.tsv)',text.encode('utf-8-sig'),'robot_combinacoes.tsv','text/tab-separated-values',on_click='ignore')
            d2.download_button('Baixar conferência (.csv)',audit_csv(rows),'conferencia_fatores.csv','text/csv',on_click='ignore')
            d3.download_button('Salvar entradas (.json)',dump_project(p),'projeto_combinacoes.json','application/json',on_click='ignore')
            with st.expander('Conferir uma combinação',expanded=True):
                ci=st.selectbox('Combinação',range(len(rows)),format_func=lambda i:rows[i].name,key='inspect_'+result.signature+'_'+'_'.join(families))
                c=rows[ci]
                st.write(RULES[c.family]);st.caption('Origens principais que produzem esta combinação: '+', '.join(c.leaders))
                st.dataframe(pd.DataFrame(c.detail).rename(columns={'case':'Caso','name':'Ação','origin':'Origem','gamma':'γ','reduction':'ψ / redução','coefficient':'Coeficiente','role':'Papel','source_gamma':'Fonte γ','source_psi':'Fonte ψ','notes':'Justificativa'}),hide_index=True,width='stretch')
                st.caption('Quando rotas diferentes geram coeficientes idênticos, a tabela mostra a primeira rota; a lista de origens registra as alternativas equivalentes.')
        else:st.info('Selecione ao menos uma família para exportar.')
    elif 'result' not in st.session_state:st.info('Preencha as entradas e clique em Gerar combinações. Entradas incompletas ou conflitantes serão indicadas aqui.')

with tab_bank:
    st.subheader('Banco normativo e decisões explícitas')
    st.caption('NBR 8800:2024 com errata de 2025 · NBR 14762:2010 · NBR 8681:2025. Valores por categoria, sem substituição automática entre normas.')
    std=pick('Consultar norma',BANK['standards'],p['standard'] or BANK['standards'][0],'bank_standard')
    st.markdown('**Coeficientes γ**')
    st.dataframe(pd.DataFrame([{'Tipo':TYPES.get(r['type'],{}).get('label',r['type']),'Natureza':r['nature'],**dict(zip(['Normal desf.','Normal fav.','Especial/constr. desf.','Especial/constr. fav.','Excepcional desf.','Excepcional fav.'],r['values'])),'Fonte':r['source'],'Observação':r.get('note','')} for r in BANK['gamma'] if r['standard']==std]),hide_index=True,width='stretch')
    st.markdown('**Fatores de combinação ψ**')
    st.dataframe(pd.DataFrame([{'Categoria':PROFILES[r['profile']]['label'],**dict(zip(['ψ0','ψ1','ψ2'],r['values'])),'Fonte':r['source'],'Observação':r.get('note','')} for r in BANK['psi'] if r['standard']==std]),hide_index=True,width='stretch')
    st.caption('Campos favoráveis de Q não são utilizados: a ausência da ação é controlada pelas opções de presença. Campos não aplicáveis a E também não são utilizados.')
    for f,label in FAMILIES.items():st.write(f'**{label}:** {RULES[f]}')
    st.markdown('''A escolha de **ψ efetivo** nas situações especiais, de construção e excepcionais deve considerar duração e condição normativa; o aplicativo exige escolha e justificativa. A opção “principal” especial/de construção vale para aquela situação; as demais variáveis entram como acompanhantes.

As permanentes da **mesma origem** variam juntas. Na ponderação agrupada, todas as permanentes diretas compartilham a ponderação e devem ter controles coerentes. Compatibilidade não força simultaneidade; para isso use a mesma origem apenas quando se tratar da mesma ação física, ou a presença obrigatória com justificativa.

A rotina cobre combinações estáticas com fatores escalares. Não trata automaticamente sismo, incêndio, fadiga, análise não linear, imperfeições ou regras específicas externas ao banco. Não é uma memória de cálculo.''')
    st.caption(f'Banco {BANK["version"]} · identificação {BANK_HASH[:16]}')

with tab_help:
    st.subheader('Do cadastro ao Robot')
    st.markdown('''1. Escolha a norma, as famílias e a forma de ponderação no menu lateral.
2. Cadastre cada caso com o **mesmo número usado no Robot**. Marque as famílias aplicáveis.
3. Dê uma origem distinta a cada ação independente. Para quatro ventos alternativos, use quatro origens e um mesmo grupo incompatível.
4. Para reduzir combinações, ajuste ponderações de G, presença de Q ou elegibilidade como principal. Registre a justificativa técnica.
5. Clique em **Gerar combinações**, confira fatores e copie o bloco tabulado para a coluna **Nome** da tabela do Robot. Faça a primeira colagem em uma cópia do modelo e confira os coeficientes e a classificação das famílias.
6. Baixe o projeto JSON para continuar depois. O TSV pode ser aberto no Excel como texto separado por tabulações e também copiado para o Robot.

**Exemplo didático:** 1 permanente, 1 sobrecarga e 4 ventos incompatíveis. G com duas ponderações; variáveis com presença/ausência. Resultado esperado: 28 ELU normais, 14 ELS raras, 10 ELS frequentes e 2 ELS quase permanentes.

**Por que pode haver muitas combinações?** Além da variável principal, o motor considera presenças e ausências permitidas e as ponderações de G. Os limites interrompem a geração inteira: uma saída parcial nunca é liberada como completa.

**Dados da sessão:** o aplicativo não grava automaticamente seus projetos em um banco. Em uma publicação Streamlit, o servidor processa os dados enviados. Configure a visibilidade do aplicativo conforme o uso pretendido.''')
