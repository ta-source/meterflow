document.addEventListener("DOMContentLoaded", () => {

let s = document.getElementById("signupForm");
if(s){
s.onsubmit = async e=>{
e.preventDefault();
let r = await fetch("/signup",{method:"POST",body:new FormData(s)});
let d = await r.json();
alert(d.message);
};
}

let l = document.getElementById("loginForm");
if(l){
l.onsubmit = async e=>{
e.preventDefault();
let r = await fetch("/login",{method:"POST",body:new FormData(l)});
let d = await r.json();
alert(d.message);
if(d.message==="Login success") location="/dashboard";
};
}

});

async function add(){
await fetch("/add",{method:"POST",body:new URLSearchParams({value:val.value})});
load();
}

async function load(){
let r = await fetch("/data");
let d = await r.json();
let list = document.getElementById("list");
list.innerHTML="";
d.forEach(x=>{
let li=document.createElement("li");
li.innerText=`${x.value} (usage ${x.usage})`;
list.appendChild(li);
});
}