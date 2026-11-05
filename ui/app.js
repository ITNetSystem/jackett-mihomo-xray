const $=selector=>document.querySelector(selector);
let state=null;
const labels={manual:'Вручную',auto:'Авто',fallback:'Резерв'};
function escapeText(value){const node=document.createElement('span');node.textContent=value;return node.innerHTML}
function render(data){
  state=data;
  $('.health').classList.toggle('online',data.ready);
  $('#health-text').textContent=data.ready?'Xray работает':'Нет подключения';
  $('#core').textContent=data.core;$('#version').textContent=data.version;
  $('#updated').textContent=data.lastRefresh?new Date(data.lastRefresh*1000).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}):'—';
  document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-checked',String(button.dataset.mode===data.mode)));
  $('#count').textContent=data.nodes.length;
  $('#nodes').innerHTML=data.nodes.map(node=>`<button class="node" type="button" role="radio" aria-checked="${node.id===data.selected}" data-node="${escapeText(node.id)}"><span class="node-icon">${escapeText(node.name.slice(0,2).toUpperCase())}</span><span class="node-copy"><strong>${escapeText(node.name)}</strong><small>${labels[data.mode]} · Xray</small></span><span class="check" aria-hidden="true"></span></button>`).join('');
  $('#error').hidden=!data.error;$('#error').textContent=data.error||'';
}
async function request(path,body){
  document.body.classList.add('busy');document.querySelectorAll('button').forEach(button=>button.disabled=true);
  try{const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw new Error(data.error||'Не удалось выполнить запрос');render(data)}
  catch(error){$('#error').hidden=false;$('#error').textContent=error.message}
  finally{document.body.classList.remove('busy');document.querySelectorAll('button').forEach(button=>button.disabled=false)}
}
document.addEventListener('click',event=>{const mode=event.target.closest('[data-mode]');const node=event.target.closest('[data-node]');if(mode&&state)request('/api/state',{mode:mode.dataset.mode,selected:state.selected});if(node&&state)request('/api/state',{mode:state.mode,selected:node.dataset.node});if(event.target.closest('#refresh'))request('/api/refresh',{})});
request('/api/status');setInterval(()=>request('/api/status'),30000);
