var Exam={};
Exam.idSeed = 0;
Exam.elCache={};// 统一存储dom元素相关数据、自定义事件
var console = console || {
	log: function () {
		return false;
	}
};

var CONTEXTPATH = '';
var scripts = document.getElementsByTagName("script");
for(var i=0;i<scripts.length;i++){
	if(/.*js\/Framework\/Main\.js$/g.test(scripts[i].getAttribute("src"))){
		var jsPath = scripts[i].getAttribute("src").replace(/js\/Framework\/Main\.js$/g,'');
		if(jsPath.indexOf("/")==0||jsPath.indexOf("://")>0){
			CONTEXTPATH = jsPath;
			break;
		}
		var arr1 = jsPath.split("/");
		var path = window.location.href;
		if(path.indexOf("?")!=-1){
			path = path.substring(0,path.indexOf("?"));
		}
		var arr2 = path.split("/");
		arr2.splice(arr2.length-1,1);
		for(var i=0;i<arr1.length;i++){
			if(arr1[i]==".."){
				arr2.splice(arr2.length-1,1);
			}
		}
		CONTEXTPATH = arr2.join('/')+'/';
		break;
	}
}
/*---------------------------Server-------------------------*/
var Server = {};
Server.RequestMap = {};

Server.ContextPath = CONTEXTPATH;
Server.Pool = [];

Server.loadScript = function(url){
	document.write('<script type="text/javascript" src="' + Server.ContextPath+url + '"><\/script>') ;
}

Server.loadCSS = function(url){
	if(isGecko){
		var e = document.createElement('LINK') ;
		e.rel	= 'stylesheet' ;
		e.type	= 'text/css' ;
		e.href	= url ;
		document.getElementsByTagName("HEAD")[0].appendChild(e) ;
	}else{
		document.createStyleSheet(url);
	}
}
var isIE = navigator.userAgent.toLowerCase().indexOf("msie") != -1;
var isIE8 = !!window.XDomainRequest&&!!document.documentMode;
var isIE7 = navigator.userAgent.toLowerCase().indexOf("msie 7.0") != -1 && !isIE8;
var isIE6 = navigator.userAgent.toLowerCase().indexOf("msie 6.0") != -1;
var isGecko = navigator.userAgent.toLowerCase().indexOf("gecko") != -1;
var isOpera = navigator.userAgent.toLowerCase().indexOf("opera") != -1;
var isQuirks = document.compatMode == "BackCompat";
var isStrict = document.compatMode == "CSS1Compat";
var isBorderBox = isIE && isQuirks;

/*load css*/
Server.loadCSS("css/main.css");
Server.loadCSS("css/loading.css");
Server.loadCSS("js/plugins/flexigrid/flexigrid.css");
/*START_LOADSCRIPT*/
Server.loadScript("js/framework/jquery.min.js");
Server.loadScript("js/framework/jquery.wresize.js");
Server.loadScript("js/framework/zDrag.js");
Server.loadScript("js/framework/zDialog.js?v=1.2");
Server.loadScript("js/framework/util.js");
Server.loadScript("js/plugins/flexigrid/flexigrid2.js");
Server.loadScript("js/framework/ajax.js");
Server.loadScript("js/framework/jquery.selectbox.js");
Server.loadScript("js/Application.js?v=1.67");
//Server.loadScript("js/openshut.js");
/*END_LOADSCRIPT*/



String.prototype.startsWith = String.prototype.startWith = function(str) {
  return this.indexOf(str) == 0;
}

String.prototype.endsWith = String.prototype.endWith = function(str) {
	var i = this.lastIndexOf(str);
  return i>=0 && this.lastIndexOf(str) == this.length-str.length;
}

String.prototype.trim = function(){
	return this.replace(/(^\s*)|(\s*$)/g,"");
}

String.prototype.leftPad = function(c,count){
	if(!isNaN(count)){
		var a = "";
		for(var i=this.length;i<count;i++){
			a = a.concat(c);
		}
		a = a.concat(this);
		return a;
	}
	return null;
}

String.prototype.rightPad = function(c,count){
	if(!isNaN(count)){
		var a = this;
		for(var i=this.length;i<count;i++){
			a = a.concat(c);
		}
		return a;
	}
	return null;
}


var Cookie = {};//Cookie操作类，支持大于4K的Cookie
Cookie.Spliter = "_JerryExam_SPLITER_";
Cookie.get = function(name){
  var cs = document.cookie.split("; ");
  for(i=0; i<cs.length; i++){
	  var arr = cs[i].split("=");
	  var n = arr[0].trim();
	  var v = arr[1]?arr[1].trim():"";
	  if(n==name){
	  	return decodeURI(v);
	  }
	}
	return null;
}

Cookie.getAll = function(){
  var cs = document.cookie.split("; ");
  var r = [];
  for(i=0; i<cs.length; i++){
	  var arr = cs[i].split("=");
	  var n = arr[0].trim();
	  var v = arr[1]?arr[1].trim():"";
	  if(n.indexOf(Cookie.Spliter)>=0){
	  	continue;
	  }
	  if(v.indexOf("^"+Cookie.Spliter)==0){
	      var max = v.substring(Cookie.Spliter.length+1,v.indexOf("$"));
	      var vs = [v];
	      for(var j=1;j<max;j++){
	      	vs.push(Cookie.get(n+Cookie.Spliter+j));
	      }
	      v = vs.join('');
	      v = v.substring(v.indexOf("$")+1);
	   }
	   r.push([n,decodeURI(v)]);
	}
	return r;
}

Cookie.set = function(name, value, expires, path, domain, secure, isPart){
	if(!isPart){
		var value = encodeURI(value);
	}
	if(!name || !value){
		return false;
	}
	if(!path){
		path = Server.ContextPath;//特别注意，此处是为了实现不管当前页面在哪个路径下，Cookie中同名名值对只有一份
	}
	path = path.replace(/^\w+:\/\/[.\w]+:?\d*/g, '');//特别注意，此处是为了实现不管当前页面在哪个路径下，Cookie中同名名值对只有一份
	if(expires!=null){
	  if(/^[0-9]+$/.test(expires)){
	    expires = new Date(new Date().getTime()+expires*1000).toGMTString();
		}else{
			var date = DateTime.parseDate(expires);
			if(date){
				expires = date.toGMTString();
			}else{
		  	expires = undefined;
		  }
		}
	}
	if(!isPart){
	  Cookie.remove(name, path, domain);
	}
	var cv = name+"="+value+";"
		+ ((expires) ? " expires="+expires+";" : "")
		+ ((path) ? "path="+path+";" : "")
		+ ((domain) ? "domain="+domain+";" : "")
		+ ((secure && secure != 0) ? "secure" : "");
  if(cv.length < 4096){
		document.cookie = cv;
	}else{
		var max = Math.ceil(value.length*1.0/3800);
		for(var i=0; i<max; i++){
			if(i==0){
				Cookie.set(name, '^'+Cookie.Spliter+'|'+max+'$'+value.substr(0,3800), expires, path, domain, secure, true);
			}else{
				Cookie.set(name+Cookie.Spliter+i, value.substr(i*3800,3800), expires, path, domain, secure, true);
			}
		}
	}
  return true;
}

Cookie.remove = function(name, path, domain){
	var v = Cookie.get(name);
  if(!name||v==null){
  	return false;
  }
  if(encodeURI(v).length > 3800){
		var max = Math.ceil(encodeURI(v).length*1.0/3800);
		for(i=1; i<max; i++){
			document.cookie = name+Cookie.Spliter+i+"=;"
				+ ((path)?"path="+path+";":"")
				+ ((domain)?"domain="+domain+";":"")
				+ "expires=Thu, 01-Jan-1970 00:00:01 GMT;";
		}
	}
	document.cookie = name+"=;"
		+ ((path)?"path="+path+";":"")
		+ ((domain)?"domain="+domain+";":"")
		+ "expires=Thu, 01-Jan-1970 00:00:01 GMT;";
	return true;
};
//+---------------------------------------------------  
//| 字符串转成日期类型   
//| 格式 MM/dd/YYYY MM-dd-YYYY YYYY/MM/dd YYYY-MM-dd  
//+---------------------------------------------------  
function StringToDate(DateStr)  
{   

  var converted = Date.parse(DateStr);  
  var myDate = new Date(converted);  
  if (isNaN(myDate))  
  {   
      //var delimCahar = DateStr.indexOf('/')!=-1?'/':'-';  
      var arys= DateStr.split('-');  
      myDate = new Date(arys[0],--arys[1],arys[2]);  
  }  
  return myDate;  
}   

	//+---------------------------------------------------  
//| 比较日期差 dtEnd 格式为日期型或者 有效日期格式字符串  
//+---------------------------------------------------  
Date.prototype.DateDiff = function(strInterval, dtStart,dtEnd) {   
   if (typeof dtStart == 'string' )//如果是字符串转换为日期型  
  {   
      dtStart = StringToDate(dtStart);  
 }   
  if (typeof dtEnd == 'string' )//如果是字符串转换为日期型  
  {   
      dtEnd = StringToDate(dtEnd);  
 }  
  switch (strInterval) {   
      case 's' :return parseInt((dtEnd - dtStart) / 1000);  
      case 'n' :return parseInt((dtEnd - dtStart) / 60000);  
      case 'h' :return parseInt((dtEnd - dtStart) / 3600000);  
      case 'd' :return parseInt((dtEnd - dtStart) / 86400000);  
      case 'w' :return parseInt((dtEnd - dtStart) / (86400000 * 7));  
      case 'm' :return (dtEnd.getMonth()+1)+((dtEnd.getFullYear()-dtStart.getFullYear())*12) - (dtStart.getMonth()+1);  
     case 'y' :return dtEnd.getFullYear() - dtStart.getFullYear();  
  }  
}  ;

/**
 * 时间戳转时间格式字符串
 * @param timestamp 时间戳，支持单位 秒和毫秒
 * @param format 格式，默认yyyy-MM-dd HH:mm:ss
 * @returns {string}
 */
function timestampToTime(timestamp, format) {
	if (typeof timestamp == 'undefined' || timestamp == null || timestamp === '' || isNaN(timestamp)) {
		return '';
	}
	format = typeof format == 'undefined' || format == null || format === '' ? 'yyyy-MM-dd HH:mm:ss' : format;
	timestamp = parseInt(timestamp);
	timestamp = timestamp > 9999999999 ? timestamp : (timestamp * 1000);
	var date = new Date(timestamp);
	var year = date.getFullYear();
	var month = date.getMonth() + 1 < 10 ? ('0' + (date.getMonth() + 1)) : (date.getMonth() + 1);
	var day = date.getDate() < 10 ? ('0' + date.getDate()) : date.getDate();
	var hour = date.getHours() < 10 ? ('0' + date.getHours()) : date.getHours();
	var minute = date.getMinutes() < 10 ? ('0' + date.getMinutes()) : date.getMinutes();
	var second = date.getSeconds() < 10 ? ('0' + date.getSeconds()) : date.getSeconds();
	return format.replace('yyyy', year).replace('MM', month).replace("dd", day).replace('HH', hour).replace('mm', minute).replace('ss', second);
}


function loadingStart() {
	var Div = document.createElement("div");
	Div.setAttribute("class","ui-loading");
	var Div2 = document.createElement("div");
	Div2.setAttribute("class","ui-loading-mytext");
	Div2.innerText="加载中,请稍后......";
	var chidDiv = document.createElement("div");
	chidDiv.setAttribute("class","ui-loading-mask")
	Div.appendChild(Div2)
	Div.appendChild(chidDiv)
	document.body.appendChild(Div)
	console.log("2222")
}


function loadingEnd() {
	var Div = document.getElementsByClassName("ui-loading");
	while(Div[0].hasChildNodes()) //当div下还存在子节点时 循环继续
	{
		Div[0].removeChild(Div[0].firstChild);
	}
	var par = Div[0].parentNode;
	par.removeChild(Div[0])
}








