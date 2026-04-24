
var fileUpload_img;
var fileUpload_isinit = false;
var fileUpload_suffixs;
var fileUpload_file;
//参数对象
function fileUpload(img, forms, file, suffix) {
	
	this.fileUpload_suffixs = suffix || ["jpg"];
	this.fileUpload_img = img;
	this.fileUpload_file = file;
	var ievesion = 0;
	if(navigator.userAgent.indexOf("MSIE")>0) {
		ievesion = IeVesion();
	}else{
		ievesion = 8;//
	}
	if(ievesion >= 7){
		_load_fileUload(img, forms, file);
	}else{
		if(_validateUpFile(file))
		jQuery("#"+img).attr("src",jQuery("#"+file).val());
	}
}

//获得ie版本
function IeVesion() {
	var Sys = {};
	var ua = navigator.userAgent.toLowerCase();
	var s;
	(s = ua.match(/msie ([\d.]+)/)) ? Sys.ie = s[1] : (s = ua.match(/firefox\/([\d.]+)/)) ? Sys.firefox = s[1] : (s = ua.match(/chrome\/([\d.]+)/)) ? Sys.chrome = s[1] : (s = ua.match(/opera.([\d.]+)/)) ? Sys.opera = s[1] : (s = ua.match(/version\/([\d.]+).*safari/)) ? Sys.safari = s[1] : 0;
	var ieversion;
	if (Sys.ie) {
		ieversion = parseInt(Sys.ie);
		if (ieversion <= 9) {
			return ieversion;
		}
	} else {
		if (Sys.firefox) {
			ieversion = Sys.firefox; 
//setIsTextReadOnly(true); 
		} else {
			if (Sys.chrome) {
				ieversion = Sys.chrome;
			} else {
				if (Sys.opera) {
					ieversion = Sys.opera;
				} else {
					if (Sys.safari) {
						ieversion = Sys.safari;
					}
				}
			}
		}
	}
}
function _load_fileUload(img, forms, file) {
	if (!_validateUpFile(file)) {
		var o = document.getElementById(file);
		if (!!document.all) {
			o.select();
			document.execCommand("delete");
		} else {
			o.value = "";
		}
		return;
	}
	var zyxm = jQuery("#zyxm").val();
	if(zyxm == '' || zyxm == undefined){
		alert("请先选择作业项目");
		var o = document.getElementById(file);
		if (!!document.all) {
			o.select();
			document.execCommand("delete");
		} else {
			o.value = "";
		}
		return;
	}

	jQuery.post('/isLogin.do', {}, function (data) {
		if (data.code == 0 && data.isLogin == 1) {
			var fm = jQuery("#" + forms);
			if (!fileUpload_isinit) {
				fileUpload_init(fm);//初始化
			}
			//保留原有form属性
			var fmparams = {"action":fm.attr("action"), "method":fm.attr("method"), "enctype":fm.attr("enctype"), "onsubmit":fm.attr("onsubmit"), "target":fm.attr("target") || "_self"};
			//设置上传图片的属性
			fm.attr({"action":"uploadksimg.do?suffix=" + fileUpload_suffixs + "&filename=" + file + "&zyxm=" + jQuery("#zyxm").val(), "method":"post", "enctype":"multipart/form-data", "onsubmit":"return true", "target":"__fileupload_frame"});
			try{
				document.getElementById(forms).submit();
				jQuery("#__fileupload_frame").html("");
			}catch(err){
				alert(err.message);
			}finally{
				fm.attr(fmparams);//初始化原有的参数
			}
		} else {
			jQuery.showVerify(function (siteX) {
				jQuery('#siteX').val(siteX);

				var fm = jQuery("#" + forms);
				if (!fileUpload_isinit) {
					fileUpload_init(fm);//初始化
				}
				//保留原有form属性
				var fmparams = {"action":fm.attr("action"), "method":fm.attr("method"), "enctype":fm.attr("enctype"), "onsubmit":fm.attr("onsubmit"), "target":fm.attr("target") || "_self"};
				//设置上传图片的属性
				fm.attr({"action":"uploadksimg.do?suffix=" + fileUpload_suffixs + "&filename=" + file + "&zyxm=" + jQuery("#zyxm").val()
						+ "&verifyType=" + jQuery("#hubeiZwfwType").val() + "&verifyUuid=" + jQuery("#verifyUuid").val()
					, "method":"post", "enctype":"multipart/form-data", "onsubmit":"return true", "target":"__fileupload_frame"});
				try{
					document.getElementById(forms).submit();
					jQuery("#__fileupload_frame").html("");
				}catch(err){
					alert(err.message);
				}finally{
					fm.attr(fmparams);//初始化原有的参数
					if (jQuery("#verifyUuid")) {
						jQuery("#verifyUuid").val("");
					}
				}
			});
		}
	}, 'json');
}

function fileUpload_init(fm) {
	fileUpload_isinit = true;
	var str = "<iframe name='__fileupload_frame' id=\"__fileupload_frame\" style=\"display: none;\"></iframe>";
	fm.append(str);//插入iframe
}
function _validateUpFile(val) {
	var suffixs = fileUpload_suffixs;
	var val = jQuery("#" + val).val();
	if (val == "") {
		//alert("请选择文件！");
		return false;
	}
	var suffix = val.substr(val.lastIndexOf(".") + 1, val.length);
	for (i = 0; i < suffixs.length; i++) {
		if (suffix.toLowerCase() == suffixs[i].toLowerCase()) {
			return true;
		}
	}
	jQuery("#" + fileUpload_file).val("");
	alert("\u8bf7\u4e0a\u4f20\u3010" + suffixs + "\u3011\u683c\u5f0f\u6587\u4ef6\uff01");
	return false;
}
var _upload_callbacks = function (path, info) {
	if (info == "1") {
		//alert("上传成功！");
		jQuery("#" + fileUpload_img).attr("src", path);
	} else {
		jQuery("#" + fileUpload_file).val("");
		alert("\u4e0a\u4f20\u5931\u8d25\uff01\u63d0\u793a\uff1a\u3010" + info + "\u3011");
	}
	//jQuery("#__fileupload_frame").remove();
};


