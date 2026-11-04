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
                f'<h1>{safe(label)}</h1></div><div class="identity-chip">{safe(user)}<small>{safe(role)}</small></div></div>',unsafe_allow_html=True)
