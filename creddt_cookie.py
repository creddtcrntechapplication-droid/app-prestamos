"""Cookie propia de CREDDT, separada de otras aplicaciones y sin contraseña."""
import uuid
import streamlit as st
JS = r"""
export default function(component) {
  const {data, parentElement, setStateValue} = component;
  const host = parentElement.host || parentElement;
  if (host.dataset.request === data.request) return;
  host.dataset.request = data.request;
  const name = 'creddt_device_session';
  const read = () => document.cookie.split('; ').find(v => v.startsWith(name+'='))?.slice(name.length+1) || '';
  const secure = location.protocol === 'https:' ? '; Secure' : '';
  let ok = true;
  try {
    if (data.command === 'clear') document.cookie = name+'=; Path=/; Max-Age=0; SameSite=Strict'+secure;
    if (data.command === 'set' && /^[A-Za-z0-9_-]{43}$/.test(data.token)) {
      document.cookie = name+'='+data.token+'; Path=/; Expires='+new Date(data.expires*1000).toUTCString()+'; SameSite=Strict'+secure;
      ok = read() === data.token;
    }
    setStateValue('result', {request:data.request, token:read(), ok});
  } catch (_) { setStateValue('result', {request:data.request, token:'', ok:false}); }
}
"""
_bridge=st.components.v2.component('creddt_device_session',js=JS)

def queue(command,token='',expires=0):
    st.session_state['_creddt_device_command']={'command':command,'token':token,'expires':expires,'request':uuid.uuid4().hex}

def browser():
    if '_creddt_device_command' not in st.session_state:queue('read')
    command=st.session_state['_creddt_device_command']
    result=_bridge(data=command,key='_creddt_device_bridge',on_result_change=lambda:None,height=0)
    value=result.result
    if not isinstance(value,dict) or value.get('request')!=command['request']:return None
    if command['command']=='set' and not value.get('ok'):st.warning('El navegador no permitió recordar este dispositivo. Al recargar tendrás que ingresar otra vez.')
    return value
