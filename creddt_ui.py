"""Componentes comunes de presentación, sin consultas ni escrituras financieras."""
from pathlib import Path
import html
import re
import pandas as pd
import streamlit as st
from creddt_finance import calendario_normal

def styles():
    st.markdown('<style>'+Path(__file__).with_name('creddt_theme.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)

def quote_preview(quote, fecha_inicio, currency):
    cols=st.columns(3)
    for col,label,key in zip(cols,['Capital','Valor de cada cuota','Total de cuotas programadas'],['capital','cuota','total']):
        col.metric(label,currency(quote[key]))
    st.caption(f"Tasa mensual pactada: {quote['tasa_mensual']*100:.2f} %. {quote['cuotas']} pagos cada "
               f"{'15' if quote['frecuencia']=='Quincenal' else '30'} días exactos. Redondeo vigente a miles de pesos.")
    if quote['total']<quote['capital']:
        st.error('Estas cuotas no cubren el capital prestado. No se permite registrar este calendario: revisa tasa, frecuencia y plazo.')
    else:
        st.caption('Diferencia entre cuotas programadas y capital: '+currency(quote['diferencia_total_capital'])+'. Es una proyección, no interés recaudado.')
    with st.expander('Calendario antes de confirmar'):
        data=pd.DataFrame(calendario_normal(quote,fecha_inicio))
        data['Valor (COP)']=data['Valor (COP)'].map(currency)
        st.dataframe(data,hide_index=True,use_container_width=True)

def page_context(label,user,role):
    label=re.sub(r'^[^\w]+','',str(label))
    safe=lambda x:html.escape(str(x))
    st.markdown(f'<div class="workspace-head"><div><span class="workspace-kicker">CREDDT / CRNTECH</span>'
                f'<h1>{safe(label)}</h1></div></div>',unsafe_allow_html=True)


def compact_navigation(allowed, logout):
    """Agrupa destinos autorizados conservando el destino canónico y su URL."""
    groups = [
        ('Inicio', 'home', ['📊 Resumen']),
        ('Clientes', 'group', ['👥 Clientes']),
        ('Créditos', 'description', ['🆕 Nuevo crédito', '📄 Detalle por crédito', '🗂️ Cartera por cliente']),
        ('Cobros', 'payments', ['💰 Pagos']),
        ('Análisis', 'monitoring', ['📈 Proyección', '🧮 Simulador']),
    ]
    current = st.session_state.menu_activo
    def go(destination):
        st.session_state.menu_activo = destination
    role = {'ADMIN':'Administrador','ASESOR':'Asesor','CONSULTA':'Consulta'}.get(st.session_state.get('rol'), 'Usuario')
    user = str(st.session_state.get('usuario', 'Usuario'))
    st.markdown('<div class="compact-brand">CREDDT<span>CRNTECH · Gestión de créditos</span></div>', unsafe_allow_html=True)
    with st.popover(user, icon=':material/account_circle:', use_container_width=True):
        st.caption(role)
        st.button('Mi cuenta', icon=':material/manage_accounts:', key='profile_account', on_click=go, args=('🔒 Mi cuenta',), use_container_width=True)
        if '👤 Usuarios' in allowed:
            st.button('Administrar usuarios', icon=':material/group_add:', key='profile_users', on_click=go, args=('👤 Usuarios',), use_container_width=True)
        st.divider()
        if st.button('Cerrar sesión', icon=':material/logout:', key='btn_logout_sidebar', use_container_width=True):
            logout()
    st.caption('ESPACIO DE TRABAJO')
    with st.container(key='compact_navigation'):
        for title, icon, destinations in groups:
            destinations = [x for x in destinations if x in allowed]
            if not destinations:
                continue
            active = current in destinations
            st.button(title, icon=f':material/{icon}:', key='nav_'+title,
                      type='primary' if active else 'tertiary', use_container_width=True,
                      on_click=go, args=(destinations[0],))
            if active and len(destinations)>1:
                # Solo se muestran las opciones del área actual.
                st.session_state['subnav_'+title] = current
                st.radio('Opciones de '+title, destinations, index=destinations.index(current),
                         key='subnav_'+title, format_func=lambda x:x.split(' ',1)[-1],
                         on_change=lambda k='subnav_'+title:go(st.session_state[k]), label_visibility='collapsed')


def account_identity(user, role):
    friendly = {'ADMIN':'Administrador','ASESOR':'Asesor','CONSULTA':'Consulta'}.get(role,'Usuario')
    initial = html.escape(str(user)[:1].upper() or 'U')
    st.markdown(f'<div class="account-identity"><div class="account-avatar">{initial}</div><div><span class="account-eyebrow">PERFIL PERSONAL</span><h2>{html.escape(str(user))}</h2><span class="account-role">{friendly}</span></div><span class="account-protected">Acceso privado</span></div>',unsafe_allow_html=True)
