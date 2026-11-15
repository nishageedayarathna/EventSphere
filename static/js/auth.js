// EventSphere authentication: session cookie + CSRF token
async function getCsrfToken(){
 const r=await fetch("/api/auth/csrf",{credentials:"same-origin"});
 if(!r.ok)throw new Error("Could not obtain security token.");
 return (await r.json()).csrf_token;
}
async function readJson(r){const t=await r.text();try{return t?JSON.parse(t):{};}catch{return {detail:t};}}
function message(text,isError=false){
 const el=document.getElementById("formMessage")||document.getElementById("authMessage");
 if(el){el.textContent=text;el.style.color=isError?"#b42318":"#167343";}
}
document.addEventListener("DOMContentLoaded",()=>{
 const login=document.getElementById("loginForm");
 if(login)login.addEventListener("submit",async e=>{
  e.preventDefault();const button=login.querySelector('[type="submit"]');button.disabled=true;
  try{
   const csrf=await getCsrfToken();
   const r=await fetch("/api/auth/login",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},body:JSON.stringify({email:login.email.value.trim(),password:login.password.value})});
   const d=await readJson(r);if(!r.ok)throw new Error(d.detail||"Login failed.");
   message("Login successful. Opening your dashboard...");
   location.href="/dashboard";
  }catch(err){message(err.message,true);button.disabled=false;}
 });
 const reg=document.getElementById("registerForm");
 if(reg)reg.addEventListener("submit",async e=>{
  e.preventDefault();const button=reg.querySelector('[type="submit"]');button.disabled=true;
  const full_name=reg.querySelector("#name").value.trim(),email=reg.email.value.trim(),password=reg.password.value,confirm=reg.querySelector("#confirmPassword").value;
  if(password!==confirm){message("Passwords do not match.",true);button.disabled=false;return;}
  try{
   const csrf=await getCsrfToken();
   const r=await fetch("/api/auth/register",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},body:JSON.stringify({full_name,email,password})});
   const d=await readJson(r);if(!r.ok)throw new Error(d.detail||"Registration failed.");
   message("Registration successful. Redirecting to login...");
   setTimeout(()=>location.href="/login",900);
  }catch(err){message(err.message,true);button.disabled=false;}
 });
});