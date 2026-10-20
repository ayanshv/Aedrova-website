(()=>{
let theme='light', allowPreferences=false;
try {
  allowPreferences=JSON.parse(localStorage.getItem('aedrova-storage-choice'))==='preferences';
  if(allowPreferences){
    const saved=JSON.parse(localStorage.getItem('aedrova-theme'));
    theme=saved==='dark'?'dark':saved==='system'&&matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';
  }
}catch{}
document.documentElement.dataset.theme=theme;
document.querySelector('.theme-toggle').addEventListener('click',()=>{
  theme=document.documentElement.dataset.theme==='dark'?'light':'dark';
  document.documentElement.dataset.theme=theme;
  if(allowPreferences)try{localStorage.setItem('aedrova-theme',JSON.stringify(theme));}catch{}
});
})();
