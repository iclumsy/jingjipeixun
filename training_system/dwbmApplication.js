// JavaScript Document
//选择用人单位
function selectDwyrdw(){
	var daig = new Dialog();
	daig = Dialog.open({
        Title: "选择用人单位",
        URL: Server.ContextPath + "dwbm_selectyrdw.do",
        Width: 600,
        Height: 330,
        OKEvent: function () {
            var arry = daig.innerWin.getYrdwInfo();
            if (arry.length != 8 || arry == false) {
				return;
            } else {
				if(jQuery("#dwzzjgdm").length>0){
					jQuery("#dwzzjgdm").val(arry[1].replace("&nbsp;",""));
				}
				if(jQuery("#yrdw").length>0){
					jQuery("#yrdw").val(arry[2].replace("&nbsp;",""));
				}
				if(jQuery("#dwlxr").length>0){
					jQuery("#dwlxr").val(arry[3].replace("&nbsp;",""));
				}
				if(jQuery("#dwdz").length>0){
					jQuery("#dwdz").val(arry[5].replace("&nbsp;",""));
				}
				if(jQuery("#bak3").length>0){
					jQuery("#bak3").val(arry[4].replace("&nbsp;",""));
				}
				if(jQuery("#dwlxdh").length>0){
					jQuery("#dwlxdh").val(arry[6].replace("&nbsp;","")+" "+arry[7].replace("&nbsp;",""));
				}
			}
            daig.close();
		}
	});
}
dwbm_bindselectpxjg= function(id, value,jgdm,status) {
	var bindobject = jQuery("#" + id);
	//如何不是考试机构就取传过来的值
	var ijgdm = dwbm_jglb == "9001"?dwbm_jgdm:jgdm;
	var ispx = false;
	var ajax = new Ajax(Server.ContextPath+"dwbm_querypxjg.do?jgdm="+ijgdm, function(data) {
		if (data) {
			if(data == null || data.length == 0){
				ispx = false;
				return;
			}
			ispx = true;
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.setAsync(false);
	ajax.submit();
	return ispx;
};


// 焊接方法
function checkValue(obj,id){
	var v_hjff=jQuery("#" + id).val();
    if (obj.checked) {
        v_hjff += "," + obj.value;
    } else {
        v_hjff = v_hjff.replace("," + obj.value, "");
	}
	/*if(v_hjff.substring(0,1)==","){	
		v_hjff=v_hjff.substring(1);
	}*/

	jQuery("#" + id).val(v_hjff);
}

// 查询焊接方法项目权限
dwbm_queryHjff = function (id, defaultvalue, jgdm, value, status, isLoadKs, fzjgdm) {
    var ksbmlb = (typeof bmlb == "undefined") ? '' : bmlb;
    var load = (typeof isLoadKs == "undefined") ? '' : isLoadKs;
    var fzjg = (typeof fzjgdm == "undefined") ? '' : fzjgdm;
    var ls_status = (typeof status == "undefined") ? "0" : status;
    var bindobject = jQuery("#" + id);
    var objStr = "";
    if (defaultvalue == null || defaultvalue == '') {
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjff.do", function (data) {
            if (data) {
                bindobject.empty();
                jQuery("#hjff").val('');
                for (var i = 0; i < data.length; i++) {
                    objStr = objStr + "<li><input type='checkbox' id='hjff1' name='hjff1' value='" + data[i].value + "' onchange='checkValue(this,\"hjff\")' />" + data[i].name + "</li>";
                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.add("isLoadKs", load);
        ajax.add("fzjgdm", fzjg);
        ajax.add('bmlb', ksbmlb);
        ajax.setAsync(false);
        ajax.submit();
    } else {
        jQuery("#hjff").val("," + defaultvalue);
        var defaultHjff = defaultvalue.split(",");
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjff.do", function (data) {
            if (data) {
                bindobject.empty();
                for (var i = 0; i < data.length; i++) {
                    var checkhjff = false;
                    for (var j = 0; j < defaultHjff.length; j++) {
                        if (defaultHjff[j] == data[i].value) {
                            checkhjff = true;
                        }
                    }
                    if (checkhjff) {
                        objStr = objStr + "<li><input type='checkbox' id='hjff1' name='hjff1' checked='checked'  value='" + data[i].value + "' onchange='checkValue(this,\"hjff\")' />" + data[i].name + "</li>";
                    } else {
                        objStr = objStr + "<li><input type='checkbox' id='hjff1' name='hjff1' value='" + data[i].value + "' onchange='checkValue(this,\"hjff\")' />" + data[i].name + "</li>";
                    }
                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.add("isLoadKs", load);
        ajax.add("fzjgdm", fzjg);
        ajax.add('bmlb', ksbmlb);
        ajax.setAsync(false);
        ajax.submit();
    }
    if (objStr == null || objStr == '') {
        bindobject.prepend("<ul>该机构没有焊接方法的考试权限</ul>")
    } else {
        bindobject.prepend("<ul>" + objStr + "</ul>");
    }
};
// 焊接方法对应的 金属类别	
dwbm_queryHjJscldl = function (id, defaultvalue, jgdm, value, status, isLoadKs, fzjgdm) {
    var ksbmlb = (typeof bmlb == "undefined") ? '' : bmlb;
    var load = (typeof isLoadKs == "undefined") ? '' : isLoadKs;
    var fzjg = (typeof fzjgdm == "undefined") ? '' : fzjgdm;
    var ls_status = (typeof status == "undefined") ? "0" : status;
    var bindobject = jQuery("#" + id);
    var objStr = "";
    if (defaultvalue == null || defaultvalue == '') {
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjJscldl.do", function (data) {
            if (data) {
                if (data) {
                    bindobject.empty();
                    for (var i = 0; i < data.length; i++) {
                        objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' value='" + data[i].value + "' />" + data[i].name + "</li>";
                    }

                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.add("isLoadKs", load);
        ajax.add("fzjgdm", fzjg);
        ajax.add("bmlb", ksbmlb);
        ajax.setAsync(false);
        ajax.submit();
    } else {
        var defaultHjff = defaultvalue.split(",");
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjJscldl.do", function (data) {
            if (data) {
                bindobject.empty();
                for (var i = 0; i < data.length; i++) {
                    var checkhjff = false;
                    for (var j = 0; j < defaultHjff.length; j++) {
                        if (defaultHjff[j] == data[i].value) {
                            checkhjff = true;
                        }
                    }
                    if (checkhjff) {
                        objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' checked='checked'  value='" + data[i].value + "' />" + data[i].name + "</li>";
                    } else {
                        objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' value='" + data[i].value + "' />" + data[i].name + "</li>";
                    }
                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.add("isLoadKs", load);
        ajax.add("fzjgdm", fzjg);
        ajax.add("bmlb", ksbmlb);
        ajax.setAsync(false);
        ajax.submit();
    }
    if (objStr == null || objStr == '') {
        bindobject.prepend("<ul>该机构没有母材种类的考试权限</ul>")
    } else {
        bindobject.prepend("<ul>" + objStr + "</ul>");
    }
};


//发证机构焊接方法
dwbm_queryHjff_fz = function(id, defaultvalue,jgdm,value, status) {
    var ls_status = (typeof status == "undefined") ? "0" : status;
    var bindobject = jQuery("#" + id);
    var objStr = "";
    if (defaultvalue == null || defaultvalue == '') {
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjff_fzjg.do", function (data) {
            if (data) {
                bindobject.empty();
                for (var i = 0; i < data.length; i++) {
                    objStr = objStr + "<li><input type='checkbox' id='hjff' name='hjff' value='" + data[i].value + "' />" + data[i].name + "</li>";
                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.setAsync(false);
        ajax.submit();
    } else {
        var defaultHjff = defaultvalue.split(",");
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjff_fzjg.do", function (data) {
            if (data) {
                bindobject.empty();
                for (var i = 0; i < data.length; i++) {
                    var checkhjff = false;
                    for (var j = 0; j < defaultHjff.length; j++) {
                        if (defaultHjff[j] == data[i].value) {
                            checkhjff = true;
                        }
                    }
                    if (checkhjff) {
                        objStr = objStr + "<li><input type='checkbox' id='hjff' name='hjff' checked='checked'  value='" + data[i].value + "' />" + data[i].name + "</li>";
                    } else {
                        objStr = objStr + "<li><input type='checkbox' id='hjff' name='hjff' value='" + data[i].value + "' />" + data[i].name + "</li>";
                    }
                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.setAsync(false);
        ajax.submit();
    }
    if (objStr == null || objStr == '') {
        bindobject.prepend("<ul>该机构没有焊接方法的考试权限</ul>")
    } else {
        bindobject.prepend("<ul>" + objStr + "</ul>");
    }
};
// 发证机构焊接方法对应的 金属类别	
dwbm_queryHjJscldl_fz = function (id, defaultvalue, jgdm, value, status) {
    var ls_status = (typeof status == "undefined") ? "0" : status;
    var bindobject = jQuery("#" + id);
    var objStr = "";
    if (defaultvalue == null || defaultvalue == '') {
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjJscldl_fzjg.do", function (data) {
            if (data) {
                if (data) {
                    bindobject.empty();
                    for (var i = 0; i < data.length; i++) {
                        objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' value='" + data[i].value + "' />" + data[i].name + "</li>";
                    }

                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.setAsync(false);
        ajax.submit();
    } else {
        var defaultHjff = defaultvalue.split(",");
        var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjJscldl_fzjg.do", function (data) {
            if (data) {
                bindobject.empty();
                for (var i = 0; i < data.length; i++) {
                    var checkhjff = false;
                    for (var j = 0; j < defaultHjff.length; j++) {
                        if (defaultHjff[j] == data[i].value) {
                            checkhjff = true;
                        }
                    }
                    if (checkhjff) {
                        objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' checked='checked'  value='" + data[i].value + "' />" + data[i].name + "</li>";
                    } else {
                        objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' value='" + data[i].value + "' />" + data[i].name + "</li>";
                    }
                }
            }
        });
        ajax.add("jgdm", jgdm);
        ajax.setAsync(false);
        ajax.submit();
    }
    if (objStr == null || objStr == '') {
        bindobject.prepend("<ul>该机构没有母材种类的考试权限</ul>")
    } else {
        bindobject.prepend("<ul>" + objStr + "</ul>");
    }
};

// 金属类别 对应的明细信息	
var dwbm_queryHjJscldlMx = function(id, jscldl,value, status) {
    var ls_status = (typeof status == "undefined") ? "0" : status;
    var bindobject = jQuery("#" + id);
    var ajax = new Ajax(Server.ContextPath + "dwbm_queryHjJscldlMx.do?jgdm=" + dwbm_jgdm, function (data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption([{
                value: "",
                name: "--请选择--"
            }], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("jscldl", jscldl);
    ajax.setAsync(false);
    ajax.submit();
};
//绑定代码 作业种类
dwbm_bindselectzyzl= function(id, value,ishk,bmlb, status) {
	if(ishk==null||ishk=="") {ishk='0';}
	var bf = "bmfs" in window ? bmfs:'0';
	var jg = bf == '2'?jgdm:dwbm_jgdm;
	var lb = bf == '2'?'9001':dwbm_jglb;
	var planid = "";
	if(typeof(dwbm_planid) != "undefined" && dwbm_planid != null){
		planid = dwbm_planid;
	}
	var bindobject = jQuery("#" + id);
    var bmid = jQuery("#bmid").val();
    var bmparam = bmid ? ("&bmid=" + bmid) : "";
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyzlbyjg.do?jgdm="+jg+"&jglb="+lb+"&planid="+planid+bmparam, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("ishk",ishk);

	if(bmlb!=undefined){
		ajax.add("bmlb",bmlb);
	}
	ajax.setAsync(false);
	ajax.submit();
};

//绑定代码 作业项目
dwbm_bindselectzyxm= function(id, zyzlval,value,bmlb, status) {
	var bindobject = jQuery("#" + id);
	var bf = "bmfs" in window ? bmfs:'0';
	var jg = bf == '2'?jgdm:dwbm_jgdm;
	var lb = bf == '2'?'9001':dwbm_jglb;
	var planid = "";
	if(typeof(dwbm_planid) != "undefined" && dwbm_planid != null){
		planid = dwbm_planid;
	}
    var bmid = jQuery("#bmid").val();
    var bmparam = bmid ? ("&bmid=" + bmid) : "";
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyxmbyjg.do?jgdm="+jg+"&jglb="+lb+"&planid="+planid+bmparam + "&zyxm="+value+ "&yxzt="+yxzt, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
            if (value != '0802' && value != '0805' && value != '0806'
                && value != '0807' && value != '0808' && value != '0809' && value != '0810'
				&& value != '0811' && value != '0904' && value != '0202' && value != '0203' && value != '0704' && value != '0792') {
                bindobject.addOption([{
                    value: "",
                    name: "--请选择--"
                }], false, false, "value", "name");
            }
			bindobject.addOption(data, false, false, "value", "name");
            if (value != '0802' && value != '0805' && value != '0806'
                && value != '0807' && value != '0808' && value != '0809' && value != '0810'
				&& value != '0811' && value != '0904' && value != '0202' && value != '0203' && value != '0704' && value != '0792') {
                bindobject.val(value);
            }
            if (value == "0904") {
                bindobject.val("0996");
            }
			if (value == "0704" || value == "0792") {
				bindobject.val("0798");
			}
            if (value != null && value != "") {
                var xm = jQuery("#zyxm").find("option:selected").text();
                if (xm != null && xm != "") {
                    var xms = xm.split(",");
                    var xmdh = "";
                    for (var i = 0; i < xms.length; i++) {
                        var dh = xms[i].substr(xms[i].indexOf("[") + 1, xms[i].indexOf("]") - xms[i].indexOf("[") - 1);
                        if (i == 0) {
                            xmdh = dh;
                        } else {
                            xmdh = xmdh + "," + dh;
                        }
                    }
                    jQuery("#zyxm_val").val(xmdh);
                }
			}
		}
	});
	ajax.add("zyzl", zyzlval);

	if(bmlb!=undefined){
		ajax.add("bmlb",bmlb);
	}
	ajax.setAsync(false);
	ajax.submit();
};
//绑定代码 作业种类(有过滤外网不能报的数据)
dwbm_bindselectzyzl_web= function(id, value,ishk,bmlb, status) {
	if(ishk==null||ishk=="") {ishk='0';}
	var bf = "bmfs" in window ? bmfs:'0';
	var jg = bf == '2'?jgdm:dwbm_jgdm;
	var lb = bf == '2'?'9001':dwbm_jglb;
	var bindobject = jQuery("#" + id);
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyzlbyjg_web.do?jgdm="+jg+"&jglb="+lb, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("ishk",ishk);
	if(bmlb){
		ajax.add("bmlb",bmlb);
	}
	ajax.setAsync(false);
	ajax.submit();
};

//绑定代码 作业项目(有过滤外网不能报的数据)
dwbm_bindselectzyxm_web= function(id, zyzlval,value,bmlb, status) {
	var bindobject = jQuery("#" + id);
	var bf = "bmfs" in window ? bmfs:'0';
	var jg = bf == '2'?jgdm:dwbm_jgdm;
	var lb = bf == '2'?'9001':dwbm_jglb;
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyxmbyjg_web.do?jgdm="+jg+"&jglb="+lb, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("zyzl", zyzlval);
	if(bmlb){
		ajax.add("bmlb",bmlb);
	}
	ajax.setAsync(false);
	ajax.submit();
};
//绑定代码 作业种类 发证机构
dwbm_bindselectfzzyzl= function(id, value,ishk, status) {
	if(ishk==null||ishk=="") {ishk='0';}
	var bindobject = jQuery("#" + id);
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyzlbyfzjg.do?jgdm="+dwbm_jgdm+"&jglb="+dwbm_jglb, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("ishk",ishk);
	ajax.setAsync(false);
	ajax.submit();
};

//绑定代码 作业项目 发证机构
dwbm_bindselectfzzyxm= function(id, zyzlval,value, status) {

	var bindobject = jQuery("#" + id);
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyxmbyfzjg.do?jgdm=" + dwbm_jgdm, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("zyzl", zyzlval);
	ajax.setAsync(false);
	ajax.submit();
};

//绑定代码 通用
//id 控件名 dictname代码，value原来的值 isroot 是否有头
var dwbm_bindselectdm = function(id, dmid,value,isroot, status) {
	var ls_status = (typeof status == "undefined") ? "0" : status;
	var bindobject = jQuery("#" + id);

	var ajax = new Ajax(Server.ContextPath+"dwbm_forDict.do", function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			if(isroot != '1'){
				bindobject.addOption( [ {
					value : "",
					name : "--请选择--"
				} ], false, false, "value", "name");
			}
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("dmtypeid", dmid);
	//ajax.add("type", dicttype);
	ajax.setAsync(false);
	ajax.submit();
};

//所有 作业种类
dwbm_bindselectzyzlall = function(id, value,status) {
	var bindobject = jQuery("#" + id);
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyzlall.do", function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.setAsync(true);
	ajax.submit();
};

//查询作业种类下所有 作业项目
dwbm_bindselectzyxmall= function(id, zyzlval,value,status) {
	var bindobject = jQuery("#" + id);
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyxmbyzyzl.do", function(data){
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("zyzl",zyzlval);
	ajax.setAsync(true);
	ajax.submit();
};

//地区代码加载
var bindSelectDqdm = function (id, value,jgdm,jglb,bmlb, status) {
	var ls_status = (typeof status == "undefined") ? "0" : status;
	var bindobject = jQuery("#" + id);
	var url = "dwbm_bindSelectDqdm.do";
	if(jgdm == null ){
		url = "bindSelectDqdm.do";
	}
	var ajax = new Ajax(Server.ContextPath+url, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.setAsync(false);
	ajax.add("jgdm",(jgdm==null?"":jgdm));
	ajax.add("jglb",(jglb==null?"":jglb));
	ajax.add("bmlb",bmlb==null?"":bmlb);
	ajax.submit();
};

bindzyxmSm= function(id, zyxmval) {
	jQuery("#zyxm_info").attr("style","display:none");
	if(zyxmval!=null&&zyxmval!=''){
		var ajax = new Ajax(Server.ContextPath+"dwbm_queryzyxmSm.do", function(data) {
            if (data) {
				jQuery("#zyxm_info").html("<ul><li>"+data[0].value+"</li></ul>");
				jQuery("#zyxm_info").attr("style","display:block");
			}
		});
		ajax.add("zyxm", zyxmval);
		ajax.setAsync(false);
		ajax.submit();
	}
};

/**
 * 根据证书发证机构或所在地区显示发证机构组合
 */
bindselectfzjgforbm = function(id,fzjgdm, xzqh, value) {
	var bindobject = jQuery("#" + id);
	var url = "dwbm_selectFzjgData.do";
	var ajax = new Ajax(Server.ContextPath+url, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.setAsync(true);
	ajax.add("fzjgdm",(fzjgdm==null?"":fzjgdm));
	ajax.add("xzqh",(xzqh==null?"":xzqh));
	ajax.submit();
};

function dwbmShowProjectDialog(url, name, option) {
	var diag = new Dialog();
	diag.Title = "特种设备作业人员考核管理平台";
	diag.Width = 500;
	diag.Height = 300;
	diag.URL = url;
	diag.ShowCloseButton = false;
	diag.OkButtonText = "确定";
	diag.OKEvent = function () {
		// if(diag.innerWin.validateForm()==false){return;};
		var zyzldm = diag.innerDoc.getElementById('zyzl').value;
		var zyxmdm = diag.innerDoc.getElementById('zyxm').value;
		dwbmVaildProject(zyzldm + "#" + zyxmdm);


		diag.close();
	};
	diag.show();
}

function dwbmselectOldCertInfo(sfzh,jgdm,zyxms){
	var vals = window.showModalDialog("dwbm_selectCertInfo.do?sfzh=" + sfzh + "&jgdm=" + jgdm + "&zyxms=" + (zyxms ? zyxms : ''), "", "dialogHeight:500px;dialogWidth:700px;help:no;center:yes;scroll:yes;");
    if (vals != null && vals != "") {
        var splits = vals.split("#");
        if (splits.length == 2) {
            //查看作业项目是否为老项目
            jQuery.get("isOldZyxm.do?zyxm=" + splits[1], function (data) {
                if (data != null && data != "") {
                    if (data.ISNEW == 0 && (data.NEW_ID == "" || data.NEW_ID == null)) {
                        jQuery("#tzsbzl").val("");
                        jQuery("#zyxm").html("");
                        jQuery("#zyxm").attr("disabled", true);
                        jQuery("#zyxm_val").val("");
                        jQuery("#zyxm").attr("title", "");
                        alert("选择的原有项目是已被取消的项目");
                    } else {
                        jQuery("#zyxm").attr("title", "");
                        if (splits[1] == "0202" || splits[1] == "0203") {
                            alert("原一级锅炉司炉变更为工业锅炉司炉；原二、三级锅炉司炉依据持证人申请或实际操作锅炉情况，变更为工业锅炉司炉或电站锅炉司炉");
						}
                        if (splits[1] == "0802" || splits[1] == "0805" || splits[1] == "0806" || splits[1] == "0807" || splits[1] == "0808" || splits[1] == "0809"
                            || splits[1] == "0810" || splits[1] == "0811") {
                            alert("直接换发。原客运索道维修(限电气维修)项目依据持证人申请可以同时换发客运索道修理、客运索道司机两个项目");
                        }
                        if (splits[1] == "0904") {
                            alert("直接换发。水上大型游乐设施操作与维修项目依据持证人申请可以同时换发大型游乐设施修理、操作两个项目");
                        }
                        jQuery("#tzsbzl").val(splits[1]);
                        jQuery("#zyzl").val(splits[0]);
                        jQuery("#zyzl").attr("disabled", true);
                        var zyxmdm = "";
                        if (data.ISNEW == 2) {
                            zyxmdm = splits[1];
                        } else {
                            zyxmdm = data.NEW_ID;
                        }
                        if (splits[1] != '0802' && splits[1] != '0805' && splits[1] != '0806'
                            && splits[1] != '0807' && splits[1] != '0808' && splits[1] != '0809' && splits[1] != '0810'
							&& splits[1] != '0811' && splits[1] != '0904' && splits[1] != '0202' && splits[1] != '0203' && splits[1] != '0704' && splits[1] != '0792') {
                            dwbm_bindselectzyxm('zyxm', splits[0], zyxmdm, 1);
                            jQuery("#zyxm").attr("disabled", true);
                        } else {
                            jQuery("#zyxm").removeAttr("disabled");
                            dwbm_bindselectzyxm('zyxm', splits[0], splits[1], 1);
						}
                    }
                }
            })
        } else {
            //查看作业项目是否为老项目
            jQuery.get("isOldZyxm.do?zyxm=" + splits[5], function (data) {
                if (data != null && data != "") {
                    if (data.ISNEW == 0 && (data.NEW_ID == "" || data.NEW_ID == null)) {
                        jQuery("#tzsbzl").val("");
                        jQuery("#zyxm").html("");
                        jQuery("#zyxm").attr("disabled", true);
                        jQuery("#zyxm_val").val("");
                        jQuery("#zyxm").attr("title", "");
                        alert("选择的原有项目是已被取消的项目");
                    } else {
                        jQuery("#zyxm").attr("title", "");
                        if (splits[5] == "0202" || splits[5] == "0203") {
                            alert("原一级锅炉司炉变更为工业锅炉司炉；原二、三级锅炉司炉依据持证人申请或实际操作锅炉情况，变更为工业锅炉司炉或电站锅炉司炉");
                        }
                        if (splits[5] == "0802" || splits[5] == "0805" || splits[5] == "0806" || splits[5] == "0807" || splits[5] == "0808" || splits[5] == "0809"
                            || splits[5] == "0810" || splits[5] == "0811") {
                            alert("直接换发。原客运索道维修(限电气维修)项目依据持证人申请可以同时换发客运索道修理、客运索道司机两个项目");
                        }
                        if (splits[5] == "0904") {
                            alert("直接换发。水上大型游乐设施操作与维修项目依据持证人申请可以同时换发大型游乐设施修理、操作两个项目");
                        }

                        if (!zyxms) {
                            if (jQuery("#sqrxm").length > 0) {
                                jQuery("#sqrxm").val(splits[0]);
                            }
                        }
                        if (jQuery("#zsbh").length > 0) {
                            jQuery("#zsbh").val(splits[1]);
                        }
                        if (jQuery("#bak4").length > 0) {
                            jQuery("#bak4").val(splits[2]);
                        }
                        if (jQuery("#fzrq").length > 0) {
                            timeMethod = 'yyyy-MM-dd';
                            document.getElementById("model").value = "切换到月";
                            jQuery("#fzrq").val(splits[3]);
                        }
                        if (jQuery("#zyzl").length > 0 && splits[4] != null && splits[4] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                            jQuery("#zyzl").val(splits[4]);
                        }
                        jQuery("#zyzl").attr("disabled", true);
                        if (jQuery("#zyxm").length > 0 && splits[5] != null && splits[5] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                            jQuery("#tzsbzl").val(splits[5]);
                            if (jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                                if (splits[5] != '0802' && splits[5] != '0805' && splits[5] != '0806'
                                    && splits[5] != '0807' && splits[5] != '0808' && splits[5] != '0809' && splits[5] != '0810'
									&& splits[5] != '0811' && splits[5] != '0904' && splits[5] != '0202' && splits[5] != '0203' && splits[5] != '0704' && splits[5] != '0792') {
                                    jQuery("#zyxm").attr("disabled", true);
                                    if (splits[8] != null && splits[8] != "") {
                                        dwbm_bindselectzyxm('zyxm', splits[4], splits[8], 1);
                                    } else {
                                        dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
                                    }
                                } else {
                                    jQuery("#zyxm").removeAttr("disabled");
                                    dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
                                }
                            } else {
                                jQuery("#zyxm").removeAttr("disabled");
                                dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
                            }
                        } else {
                            jQuery("#zyxm").val("");
                            jQuery("#zyxm_val").val("");
                        }
                        if (jQuery("#oldzyxm").length > 0) {
                            jQuery("#oldzyxm").val(splits[6]);
                        }
                    }
                }
			})
            //判断是否可以修改证书数据
            // if(splits[7]!= null && splits[7]=="0"){
            //     jQuery("#sfzh").attr("disabled",true);
            //     jQuery("#zsbh").attr("disabled",true);
            //     jQuery("#fzrq").attr("disabled",true);
            //     jQuery("#bak4").attr("disabled",true);
            // }
        }
    }
};

function dwbmVaildProject(vals) {
	if (vals != null && vals != "") {
		var splits = vals.split("#");
		if (splits.length == 2) {
			//查看作业项目是否为老项目
			jQuery.get("isOldZyxm.do?zyxm=" + splits[1], function (data) {
				if (data != null && data != "") {
					if (data.ISNEW == 0 && (data.NEW_ID == "" || data.NEW_ID == null)) {
						jQuery("#tzsbzl").val("");
						jQuery("#zyxm").html("");
						jQuery("#zyxm").attr("disabled", true);
						jQuery("#zyxm_val").val("");
						jQuery("#zyxm").attr("title", "");
						alert("选择的原有项目是已被取消的项目");
					} else {
						jQuery("#zyxm").attr("title", "");
						if (splits[1] == "0202" || splits[1] == "0203") {
							alert("原一级锅炉司炉变更为工业锅炉司炉；原二、三级锅炉司炉依据持证人申请或实际操作锅炉情况，变更为工业锅炉司炉或电站锅炉司炉");
						}
						if (splits[1] == "0802" || splits[1] == "0805" || splits[1] == "0806" || splits[1] == "0807" || splits[1] == "0808" || splits[1] == "0809"
							|| splits[1] == "0810" || splits[1] == "0811") {
							alert("直接换发。原客运索道维修(限电气维修)项目依据持证人申请可以同时换发客运索道修理、客运索道司机两个项目");
						}
						if (splits[1] == "0904") {
							alert("直接换发。水上大型游乐设施操作与维修项目依据持证人申请可以同时换发大型游乐设施修理、操作两个项目");
						}
						jQuery("#tzsbzl").val(splits[1]);
						jQuery("#zyzl").val(splits[0]);
						jQuery("#zyzl").attr("disabled", true);
						var zyxmdm = "";
						if (data.ISNEW == 2) {
							zyxmdm = splits[1];
						} else {
							zyxmdm = data.NEW_ID;
						}
						if (splits[1] != '0802' && splits[1] != '0805' && splits[1] != '0806'
							&& splits[1] != '0807' && splits[1] != '0808' && splits[1] != '0809' && splits[1] != '0810'
							&& splits[1] != '0811' && splits[1] != '0904' && splits[1] != '0202' && splits[1] != '0203' && splits[1] != '0704' && splits[1] != '0792') {
							dwbm_bindselectzyxm('zyxm', splits[0], zyxmdm, 1);
							jQuery("#zyxm").attr("disabled", true);
						} else {
							jQuery("#zyxm").removeAttr("disabled");
							dwbm_bindselectzyxm('zyxm', splits[0], splits[1], 1);
						}
					}
				}
			})
		} else {
			//查看作业项目是否为老项目
			jQuery.get("isOldZyxm.do?zyxm=" + splits[5], function (data) {
				if (data != null && data != "") {
					if (data.ISNEW == 0 && (data.NEW_ID == "" || data.NEW_ID == null)) {
						jQuery("#tzsbzl").val("");
						jQuery("#zyxm").html("");
						jQuery("#zyxm").attr("disabled", true);
						jQuery("#zyxm_val").val("");
						jQuery("#zyxm").attr("title", "");
						alert("选择的原有项目是已被取消的项目");
					} else {
						jQuery("#zyxm").attr("title", "");
						if (splits[5] == "0202" || splits[5] == "0203") {
							alert("原一级锅炉司炉变更为工业锅炉司炉；原二、三级锅炉司炉依据持证人申请或实际操作锅炉情况，变更为工业锅炉司炉或电站锅炉司炉");
						}
						if (splits[5] == "0802" || splits[5] == "0805" || splits[5] == "0806" || splits[5] == "0807" || splits[5] == "0808" || splits[5] == "0809"
							|| splits[5] == "0810" || splits[5] == "0811") {
							alert("直接换发。原客运索道维修(限电气维修)项目依据持证人申请可以同时换发客运索道修理、客运索道司机两个项目");
						}
						if (splits[5] == "0904") {
							alert("直接换发。水上大型游乐设施操作与维修项目依据持证人申请可以同时换发大型游乐设施修理、操作两个项目");
						}
						if (jQuery("#sqrxm").length > 0) {
							jQuery("#sqrxm").val(splits[0]);
						}
						if (jQuery("#zsbh").length > 0) {
							jQuery("#zsbh").val(splits[1]);
						}
						if (jQuery("#bak4").length > 0) {
							jQuery("#bak4").val(splits[2]);
						}
						if (jQuery("#fzrq").length > 0) {
							jQuery("#fzrq").val(splits[3]);
						}
						if (jQuery("#zyzl").length > 0 && splits[4] != null && splits[4] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
							jQuery("#zyzl").val(splits[4]);
						}
						jQuery("#zyzl").attr("disabled", true);
						if (jQuery("#zyxm").length > 0 && splits[5] != null && splits[5] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
							jQuery("#tzsbzl").val(splits[5]);
							if (jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
								if (splits[5] != '0802' && splits[5] != '0805' && splits[5] != '0806'
									&& splits[5] != '0807' && splits[5] != '0808' && splits[5] != '0809' && splits[5] != '0810'
									&& splits[5] != '0811' && splits[5] != '0904' && splits[5] != '0202' && splits[5] != '0203' && splits[5] != '0704' && splits[1] != '0792') {
									jQuery("#zyxm").attr("disabled", true);
									if (splits[8] != null && splits[8] != "") {
										dwbm_bindselectzyxm('zyxm', splits[4], splits[8], 1);
									} else {
										dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
									}
								} else {
									jQuery("#zyxm").removeAttr("disabled");
									dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
								}
							} else {
								jQuery("#zyxm").removeAttr("disabled");
								dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
							}
						} else {
							jQuery("#zyxm").val("");
							jQuery("#zyxm_val").val("");
						}
						if (jQuery("#oldzyxm").length > 0) {
							jQuery("#oldzyxm").val(splits[6]);
						}
					}
				}
			})
			//判断是否可以修改证书数据
			// if(splits[7]!= null && splits[7]=="0"){
			//     jQuery("#sfzh").attr("disabled",true);
			//     jQuery("#zsbh").attr("disabled",true);
			//     jQuery("#fzrq").attr("disabled",true);
			//     jQuery("#bak4").attr("disabled",true);
			// }
		}
	}
}

function dwbmselectOldCertInfo_web(sfzh){
	jQuery.get("dwbm_sfzhToCertInfo.do?sfzh="+sfzh,function(data){
		if(data == null || data.length == 0){
			return;
		}
		if(data.length > 1){
			var vals = window.showModalDialog("dwbm_selectCertInfo.do?sfzh=" + sfzh, "", "dialogHeight:260px;dialogWidth:700px;help:no;center:yes;scroll:yes;");
			if(vals != null && vals != ""){
				var splits = vals.split("#");
				if(jQuery("#sqrxm").length > 0){
					jQuery("#sqrxm").val(splits[0]);
				}
				if(jQuery("#zsbh").length > 0){
					jQuery("#zsbh").val(splits[1]);
				}
				if(jQuery("#bak4").length > 0){
					jQuery("#bak4").val(splits[2]);
				}
				if(jQuery("#fzrq").length > 0){
					jQuery("#fzrq").val(splits[3]);
				}
				if(jQuery("#zyzl").length > 0 && splits[4] != null && splits[4] != "" && jQuery("#zyzl option[value='"+splits[4]+"']").length > 0){
					jQuery("#zyzl").val(splits[4]);
				}
                if (jQuery("#zyxm").length > 0 && splits[5] != null && splits[5] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                    if (jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
						if(bmfs == "" || bmfs == '0'){
							dwbm_bindselectzyxm_web('zyxm',splits[4],splits[5],1);
						}else{
							dwbm_bindselectzyxm('zyxm',splits[4],splits[5],1);
						}
                    } else {
						if(bmfs == "" || bmfs == '0'){
							dwbm_bindselectzyxm_web('zyxm',splits[4],"",1);
						}else{
							dwbm_bindselectzyxm('zyxm',splits[4],"",1);
						}
					}
				}
				if(jQuery("#oldzyxm").length > 0){
					jQuery("#oldzyxm").val(splits[6]);
				}
			}
		}else{
			if(jQuery("#sqrxm").length > 0){
				jQuery("#sqrxm").val(data[0].CZR_XM);
			}
			if(jQuery("#zsbh").length > 0){
				jQuery("#zsbh").val(data[0].ZSBH);
			}
			if(jQuery("#bak4").length > 0){
                jQuery("#bak4").val(data[0].FZRQ);
            }
			if(jQuery("#fzrq").length > 0){
				jQuery("#fzrq").val(data[0].YXRQ);
			}
			if(jQuery("#zyzl").length > 0 && data[0].ZYZL_DM != null && data[0].ZYZL_DM != ""&& jQuery("#zyzl option[value='"+data[0].ZYZL_DM+"']").length > 0){
				jQuery("#zyzl").val(data[0].ZYZL_DM);
			}
			if(jQuery("#zyxm").length > 0 && data[0].ZYXM_DM != null && data[0].ZYXM_DM != ""&& jQuery("#zyzl option[value='"+data[0].ZYZL_DM+"']").length > 0){
				if(jQuery("#zyzl option[value='"+data[0].ZYZL_DM+"']").length > 0){
					if(bmfs == "" || bmfs == '0'){
						dwbm_bindselectzyxm_web('zyxm',data[0].ZYZL_DM,data[0].ZYXM_DM,1);
					}else{
						dwbm_bindselectzyxm('zyxm',data[0].ZYZL_DM,data[0].ZYXM_DM,1);
					}
				}else{
					if(bmfs == "" || bmfs == '0'){
						dwbm_bindselectzyxm_web('zyxm',data[0].ZYZL_DM,"",1);
					}else{
						dwbm_bindselectzyxm('zyxm',data[0].ZYZL_DM,"",1);
					}
				}
			}
			if(jQuery("#oldzyxm").length > 0){
                jQuery("#oldzyxm").val(data[0].ZYXM_MC);
			}
		}
	});
};
/**
 * 海南证书复审报名时查看该身份证用户是否有要复审的证书信息，没有谈框提示；
 * @param sfzh
 */
function showModalDialog4Train(url, obj, sFeatures,cb){
    if (window.showModalDialog == undefined) {
        if (window.trainPopupWindow != undefined) {
            if (window.trainPopupWindow != null) {
                window.trainPopupWindow.returnValue = null;
                window.trainPopupWindow.close();
                window.trainPopupWindow = null;
            }
        }
        sFeatures = sFeatures.replace(/dialogHeight/gi, "height");
        sFeatures = sFeatures.replace(/dialogWidth/gi, "width");
        sFeatures = sFeatures.replace(/dialogTop/gi, "top");
        sFeatures = sFeatures.replace(/dialogLeft/gi, "left");
        sFeatures = sFeatures.replace(/:/gi, "=");
        sFeatures = sFeatures.replace(/;/gi, ",");
        window.trainPopupWindow = window.open(url, '', sFeatures);
        window.trainPopupWindow.returnValue = null;
        window.trainPopupWindow.opener = null;
        window.trainPopupWindow.onbeforeunload = function () {
            cb(window.trainPopupWindow.returnValue);
            window.trainPopupWindow = null;
        };
    } else {
        var val = window.showModalDialog(url, obj, sFeatures);
        cb(val);
    }
}
function dwbmhn_selectOldCertInfo(sfzh){
	jQuery.get("dwbm_sfzhToCertInfo.do?sfzh="+sfzh,function(data){
        if (data == null || data.length == 0) {
			//window.parent.dwbm_cellback("系统中没有该人员的原证书信息，请联系发证机关增加该人的原证书信息!");
			alert("系统中没有该人员的原证书信息，请联系发证机关增加该人的原证书信息!");
            return;
		}
		if(data.length > 1){
			/*var vals = window.showModalDialog("dwbm_selectCertInfo.do?sfzh="+sfzh,"","dialogHeight:260px;dialogWidth:700px;help:no;center:yes;scroll:yes;");
			if(vals != null && vals != ""){
				var splits = vals.split("#");
				if(jQuery("#sqrxm").length > 0){
					jQuery("#sqrxm").val(splits[0]);
				}
				if(jQuery("#zsbh").length > 0){
					jQuery("#zsbh").val(splits[1]);
				}
				if(jQuery("#bak4").length > 0){
					jQuery("#bak4").val(splits[2]);
				}
				if(jQuery("#fzrq").length > 0){
					jQuery("#fzrq").val(splits[3]);
				}
				if(jQuery("#zyzl").length > 0 && splits[4] != null && splits[4] != "" && jQuery("#zyzl option[value='"+splits[4]+"']").length > 0){
					jQuery("#zyzl").val(splits[4]);
				}
				if(jQuery("#zyxm").length > 0 && splits[5] != null && splits[5] != ""&& jQuery("#zyzl option[value='"+splits[4]+"']").length > 0){
					if(jQuery("#zyzl option[value='"+splits[4]+"']").length > 0){
						bindselectzyxm('zyxm',splits[4],splits[5],1);
					}else{
						bindselectzyxm('zyxm',splits[4],"",1);
					}
				}
				if(jQuery("#oldzyxm").length > 0){
					jQuery("#oldzyxm").val(splits[6]);
				}
			}*/

            var url = "dwbm_selectCertInfo.do?sfzh=" + sfzh;
            var obj = "";
            var sFeatures = "dialogWidth=700px;dialogHeight=300px;help:no;center:yes;scroll:yes;";
            var cb = function (val) {
                if (val != null && val != '') {
                    var splits = val.split("#");
                    if (jQuery("#sqrxm").length > 0) {
                        jQuery("#sqrxm").val(splits[0]);
                    }
                    if (jQuery("#zsbh").length > 0) {
                        jQuery("#zsbh").val(splits[1]);
                    }
                    if (jQuery("#bak4").length > 0) {
                        jQuery("#bak4").val(splits[2]);
                    }
                    if (jQuery("#fzrq").length > 0) {
                        jQuery("#fzrq").val(splits[3]);
                    }
                    if (jQuery("#zyzl").length > 0 && splits[4] != null && splits[4] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                        jQuery("#zyzl").val(splits[4]);
                    }
                    if (jQuery("#zyxm").length > 0 && splits[5] != null && splits[5] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                        if (jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
                            dwbm_bindselectzyxm('zyxm', splits[4], splits[5], 1);
                        } else {
                            dwbm_bindselectzyxm('zyxm', splits[4], "", 1);
                        }
                    }
                    if (jQuery("#oldzyxm").length > 0) {
                        jQuery("#oldzyxm").val(splits[6]);
                    }
                }
            };
            showModalDialog4Train(url, obj, sFeatures, cb);
		}else{
			if(jQuery("#sqrxm").length > 0){
				jQuery("#sqrxm").val(data[0].CZR_XM);
			}
			if(jQuery("#zsbh").length > 0){
				jQuery("#zsbh").val(data[0].ZSBH);
			}
			if(jQuery("#bak4").length > 0){
                jQuery("#bak4").val(data[0].FZRQ);
            }
			if(jQuery("#fzrq").length > 0){
				jQuery("#fzrq").val(data[0].YXRQ);
			}
			if(jQuery("#zyzl").length > 0 && data[0].ZYZL_DM != null && data[0].ZYZL_DM != ""&& jQuery("#zyzl option[value='"+data[0].ZYZL_DM+"']").length > 0){
				jQuery("#zyzl").val(data[0].ZYZL_DM);
			}
			if(jQuery("#zyxm").length > 0 && data[0].ZYXM_DM != null && data[0].ZYXM_DM != ""&& jQuery("#zyzl option[value='"+data[0].ZYZL_DM+"']").length > 0){
				if(jQuery("#zyzl option[value='"+data[0].ZYZL_DM+"']").length > 0){
					bindselectzyxm('zyxm',data[0].ZYZL_DM,data[0].ZYXM_DM,1);
				}else{
					bindselectzyxm('zyxm',data[0].ZYZL_DM,"",1);
				}
			}
			if(jQuery("#oldzyxm").length > 0){
                jQuery("#oldzyxm").val(data[0].ZYXM_MC);
			}
		}
    });
};

//加载预计划
function loadselectplan(id,value,type,jgdm,jglb){
	var bindobject = jQuery("#" + id);
	type = type||"1";
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryPlan.do?type="+type, function(data) {
		if(data == null || data.length == 0){
			jQuery("#planlab").hide();
		}else{
			jQuery("#planlab").show();
		}
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "其它"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			if(value)
				bindobject.val(value);
		}
	});
	ajax.add("jgdm", jgdm);
	ajax.add("jglb", jglb);
	ajax.setAsync(true);
	ajax.submit();
}
/**
 * 查看是否开启联系电话必填开关
 *
 * @param id
 */
function dwbm_getTelOpenStatus(id,jglb,jgdm){
	var isOpen = false;
	var bindobject = jQuery("#"+id);
	var ajax = new Ajax("dwbm_getTelOpenStatus.do", function(data) {
		if (data != null) {
			if(data.code == 1){
				isOpen = true;
			}
		}
	});
	ajax.setAsync(false);
	ajax.add("jglb",jglb);
	ajax.add("jgdm",jgdm);
	ajax.submit();
	return isOpen;
}

/**
 * 选择行政区号
 */
var bindselectdistrictforbm = function (id, value) {
    var bindobject = jQuery("#" + id);
	var bf = "bmfs" in window ? bmfs:'0';
	var jg = bf == '2'?jgdm:dwbm_jgdm;
	var ajax = new Ajax(Server.ContextPath+"dwbm_querydistrict.do?jgdm="+jg, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.setAsync(true);
	ajax.submit();
};

/**
 * 选择行政区号
 */
var bindselectregionforbm = function (id, dwszdq, value) {

	var bindobject = jQuery("#" + id);
	var bf = "bmfs" in window ? bmfs:'0';
	var jg = bf == '2'?jgdm:dwbm_jgdm;
	var ajax = new Ajax(Server.ContextPath+"dwbm_queryregion.do?jgdm="+jg, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption( [ {
				value : "",
				name : "--请选择--"
			} ], false, false, "value", "name");
			bindobject.addOption(data, false, false, "value", "name");
			bindobject.val(value);
		}
	});
	ajax.add("dwszdq", dwszdq);
	ajax.setAsync(true);
	ajax.submit();
	if(id=="dwszdq"){//初始所在区县和所在街道信息
		jQuery("#dwszqx").empty();
		jQuery("#dwszqx").addOption( [ {
			value : "",
			name : "--请选择--"
		} ], false, false, "value", "name");

		jQuery("#dwszjd").empty();
		jQuery("#dwszjd").addOption( [ {
			value : "",
			name : "--请选择--"
		} ], false, false, "value", "name");

	}
	if(id=="dwszqx"){//初始所在街道信息
		jQuery("#dwszjd").empty();
		jQuery("#dwszjd").addOption( [ {
			value : "",
			name : "--请选择--"
		} ], false, false, "value", "name");

	}
};

var bindselectregionforSecure = function (id, dwszdq, value) {

    var bindobject = jQuery("#" + id);
    var ajax = new Ajax(Server.ContextPath+"querySecureRegion.do", function(data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption( [ {
                value : "",
                name : "--请选择--"
            } ], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("dwszdq", dwszdq);
    ajax.setAsync(true);
    ajax.submit();
    if(id=="dwszdq"){//初始所在区县和所在街道信息
        jQuery("#dwszqx").empty();
        jQuery("#dwszqx").addOption( [ {
            value : "",
            name : "--请选择--"
        } ], false, false, "value", "name");

        jQuery("#dwszjd").empty();
        jQuery("#dwszjd").addOption( [ {
            value : "",
            name : "--请选择--"
        } ], false, false, "value", "name");

    }
    if(id=="dwszqx"){//初始所在街道信息
        jQuery("#dwszjd").empty();
        jQuery("#dwszjd").addOption( [ {
            value : "",
            name : "--请选择--"
        } ], false, false, "value", "name");

    }
};
/**
 * 退休提醒
 *
 * @param {Object} sfzh
 * @param {Object} sysDate
 */
var validationCsny = function(sfzh,sysDate){
	if("dwbm_getTelOpenStatus" in window){
		var bl = dwbm_getTelOpenStatus("lxdh",dwbm_jglb,dwbm_jgdm);
		if(bl && jQuery("#lxdh").val() == ""){
			alert("请填写“联系电话(手机)”！");
			jQuery("#lxdh").focus();
			return false;
		}
	}else{
		var bl = getTelOpenStatus("lxdh");
		if(bl && jQuery("#lxdh").val() == ""){
			alert("请填写“联系电话(手机)”！");
			jQuery("#lxdh").focus();
			return false;
		}
	}
	if (jQuery("#lxdh").val().trim() != "") {
        var lxdh = jQuery("#lxdh").val();
        if (lxdh.indexOf('*') > 1) {
            lxdh = jQuery("#v_lxdh").val();
        }
        if (!(/^1(3|4|5|6|7|8|9)\d{9}$/.test(lxdh)) && !/^(\(\d{3,4}\)|\d{3,4}-|\s)?\d{7,14}$/.test(lxdh)) {
			alert("手机号码有误，请重填");
			jQuery("#lxdh").focus();
			return false;
		}
	}
	//效验文化程度是否符合项目的报名条件
	if(jQuery("#zyxm").length > 0 && jQuery("#whcd").length >0&& jQuery("#fsbj").val()!="1"){
		if(!dwbm_validateWhcd(jQuery("#zyxm").val(),jQuery("#whcd").val())){
			return false;
		}
	}
	//加提醒证书是否存在
	isKsCertExists(jQuery("#zyzl").val(),jQuery("#zyxm").val(),jQuery("#sfzh").val());

	// var nf = "";
	// var date = new Date(sysDate.split("-")[0],sysDate.split("-")[1]-1,sysDate.split("-")[2]);
	// var sex = "";
	// if(jQuery("#zjlx").val() == "1" && sfzh.length == 15){
	// 	var nf = "19"+sfzh.substr(6,6);
	// 	sex = sfzh.substring(14, 15) % 2 ? "1" : "2";
	// 	var nn = parseInt(sysDate.replaceAll("-",""))-parseInt(nf);
	// 	if(nn > 590000){
	// 		var bo = window.confirm("离退休年龄不到1年时间，确定要继续报名吗？");
	// 		return bo;
	// 	}
	// }else if(jQuery("#zjlx").val() == "1" && sfzh.length == 18){
	// 	var nf = sfzh.substr(6,8);
	// 	sex = sfzh.substring(16, 17) % 2 ? "1" : "2";
	// 	var nn = parseInt(sysDate.replaceAll("-",""))-parseInt(nf);
	// 	if(nn > 590000){
	// 		var bo = window.confirm("离退休年龄不到1年时间，确定要继续报名吗？");
	// 		return bo;
	// 	}
	// }
	return true;
};

//选择用人单位
function wbselectyrdw_fj(){
	var szdq="";
	var szqx="";
	var szjd="";
	var areacode="";
	var daig = new Dialog();
	daig= Dialog.open({
        Title: "选择用人单位",
        URL: "selectyrdw_fj.do",
        Width: 800,
        Height: 380,
        OKEvent: function () {
            var arry = daig.innerWin.getYrdwInfo();
            var flag = daig.innerDoc.getElementById('flag').value;
            if (arry.length != 13 || arry == false) {
                return;
            } else {
                if (jQuery("#dwzzjgdm").length > 0) {
                    jQuery("#dwzzjgdm").val(arry[1].replace("&nbsp;", ""));
                }
                if (jQuery("#yrdw").length > 0) {
                    jQuery("#yrdw").val(arry[2].replace("&nbsp;", ""));
                }
                if (jQuery("#dwlxr").length > 0) {
                    jQuery("#dwlxr").val(arry[3].replace("&nbsp;", ""));
                }
                if (jQuery("#dwdz").length > 0) {
                    jQuery("#dwdz").val(arry[6].replace("&nbsp;", ""));
                }
                if (jQuery("#bak3").length > 0) {
                    jQuery("#bak3").val(arry[4].replace("&nbsp;", ""));
                }
                if (jQuery("#dwlxdh").length > 0) {
                    jQuery("#dwlxdh").val(arry[7].replace("&nbsp;", "") + " " + arry[8].replace("&nbsp;", ""));
                }
                if (jQuery("#dwid").length > 0) {
                    jQuery("#dwid").val(arry[9].replace("&nbsp;", ""));
                }
                if (flag == "jyk") {//用人单位从检验库查得，要把单位信息插入考试系统用人单位表

                    var Url = Server.ContextPath + "saveUnit.do";
                    //var a=arry.serializeArray();
                    //var a=JSON.stringify(arry);
                    areacode = arry[4].replace("&nbsp;", "");
                    if (arry[1].replace("&nbsp;", "").length == 0) {
                        alert("该单位组织机构代码为空,请先补全！");
                    } else {
                        szdq = areacode.length >= 4 ? areacode.substring(0, 4) : "";
                        szqx = areacode.length >= 6 ? areacode.substring(0, 6) : "";
                        szjd = areacode.length >= 8 ? areacode.substring(0, 8) : "";
                        var jsonstr = {
                            "unitcode": arry[1].replace("&nbsp;", ""),
                            "unitname": arry[2].replace("&nbsp;", ""),
                            "unitlxr": arry[3].replace("&nbsp;", ""),
                            "dwszdq": szdq,
                            "dwszqx": szqx,
                            "dwszjd": szjd,
                            "unitarea": arry[5].replace("&nbsp;", ""),
                            "unitaddr": arry[6].replace("&nbsp;", ""),
                            "unitphone": arry[8].replace("&nbsp;", "")
                        };
                        jQuery.ajax({
                            type: "POST",
                            url: Url,
                            dataType: "json",
                            async: false,
                            data: jsonstr,
                            cache: false,
                            success: function (data, status) {
                                alert(data.o_text);
                            }
                        });
                        if (jQuery("#province").length > 0) {
                            //加载所属省份
                            bindselectdistrictforbm("province", "35");
                        }
                        if (jQuery("#dwszdq").length > 0) {
                            //加载所属市
                            //bindselectdistrictforbm("dwszdq",szdq);
                            bindselectregionforbm("dwszdq", "35", szdq);
                        }
                        if (jQuery("#dwszqx").length > 0) {
                            //加载所属区
                            bindselectregionforbm("dwszqx", szdq, szqx);
                        }
                        if (jQuery("#dwszjd").length > 0) {
                            //加载所属街道
                            bindselectregionforbm("dwszjd", szqx, areacode);
                        }

                    }
                } else {
                    if (jQuery("#province").length > 0) {
                        //加载所属省份
                        bindselectdistrictforbm("province", "35");
                    }
                    if (jQuery("#dwszdq").length > 0) {
                        //加载所属市
                        //bindselectdistrictforbm("dwszdq",arry[10].replace("&nbsp;",""));
                        bindselectregionforbm("dwszdq", "35", arry[10].replace("&nbsp;", ""));
                    }
                    if (jQuery("#dwszqx").length > 0) {
                        //加载所属区
                        bindselectregionforbm("dwszqx", arry[10].replace("&nbsp;", ""), arry[11].replace("&nbsp;", ""));

                    }
                    if (jQuery("#dwszjd").length > 0) {
                        //加载所属街道
                        bindselectregionforbm("dwszjd", arry[11].replace("&nbsp;", ""), arry[12].replace("&nbsp;", ""));
                    }
                }


            }


            daig.close();
        }
	});
}

function openUnit(){

	var diag = new Dialog();
	diag= Dialog.open({
		ID:"jykdialog",
        Title: "选择用人单位",
        URL: "dwbm_fjYrdw.do",
        Width: 680,
        Height: 500,
        OKEvent: function () {
            if (diag.innerWin.validateForm() == false) {
                return;
            }
            var arry = diag.innerWin.getString();
            var dwmc = diag.innerDoc.getElementById('dwmc').value;
            var szdq = diag.innerDoc.getElementById('dwszdq').value;
            var szqx = diag.innerDoc.getElementById('dwszqx').value;
            var szjd = diag.innerDoc.getElementById('dwszjd').value;
            var dwlxr = diag.innerDoc.getElementById('frdbr').value;//单位联系人
            var dwdz = diag.innerDoc.getElementById('jgdz').value;//单位地址
            var dwdh = diag.innerDoc.getElementById('dhhm').value;//单位电话
            //alert("gggg"+dwmc+"sss"+szdq);
            jQuery("#yrdw").val(dwmc);
            jQuery("#dwlxr").val(dwlxr);
            jQuery("#dwdz").val(dwdz);
            jQuery("#dwlxdh").val(dwdh);

            //加载所属市
            //bindselectdistrictforbm("dwszdq",szdq);
            bindselectdistrictforbm("province", "35");
            //加载所属市
            bindselectregionforbm("dwszdq", "35", szdq);
            //加载所属区
            bindselectregionforbm("dwszqx", szdq, szqx);
            //加载所属街道
            bindselectregionforbm("dwszjd", szqx, szjd);
            jQuery.ajax({
                type: "post",
                url: "fjwwbm_addyrdw.do",
                dataType: "json",
                data: arry,
                cache: false,
                async: false,
                success: function (data, status) {
                    jQuery("#dwid").val(data.dwid);
                    Dialog.alert(data.text);
                    diag.close();
                    //mygrid.flexReload();
                }
            });
        }
    });
}

//新老项目切换过渡期开始日期
function getGdqksrq() {
    var isInGdq = false;
    jQuery.ajax({
        data: {},
        async: false,
        type: "POST",
        url: "/getGdqksrq.do",
        dataType: "json",
        cache: false,
        success: function (data) {
            if (data && 1 == data.IN_GDQ) {
                isInGdq = true;
            }
        }, error: function (request, error) {
            // alert("配置日期错误！"+error);
        }
    });
    return isInGdq;
}

function checkInGdq() {
	var isInGdq = getGdqksrq();
	if(isInGdq) {
		alert("过渡期内关闭考试功能！");
		return false;
	} else {
		window.location = "examindex.do";
	}
}
function turnToUserLogin() {
    window.location = "examIdCardIndex.do";
}

function userLoginByIdCard() {
    if (window.zDialog) {
        var diag = new zDialog({
            Widht: 250,
            Height: 400,
            URL: "showUserLoginByIdCard.do"
        });

        diag.MessageTitle = "学员登录/注册";
        diag.Message = "学员登录/注册";
        diag.OKEvent = function () {
            //if (diag.innerWin.Verify.hasError())
            //	return;
            d.innerWin.encrypt();

            var dc = diag.innerWin.Form.getData("userLoginByIdCard");
            var ajax = new Ajax("loginByIdCard.do", function (data) {
                if (data) {
                    if (data.code > 0) {
                        window.location.href = "turnToUserLogin.do?idcard=" + idcard;
                        $D.close();
                    } else {
                        Dialog.alert(data.text);
                    }
                }
            });
            ajax.add(dc);
            ajax.submit();
        };
        diag.OnLoad = function () {
            //diag.innerWin.$("oldpwd").focus();
        };
        diag.show();
    } else if (window.Dialog) {
        var d = new Dialog("changepwd");
        d.Widht = 250;
        d.Height = 400;
        d.Title = "学员登录/注册";
        d.URL = "showUserLoginByIdCard.do";
        d.OkButtonText = "登录/注册";
        d.OKEvent = function () {
            var $$DW = jQuery(d.innerWin.document);

            var isRegister = jQuery("#isRegister", $$DW).val();
            if (isRegister == 1) {
                d.innerWin.encrypt();

                var idcard = jQuery("#idcard", $$DW).val();
                var phone = jQuery("#phone", $$DW).val();
                var password = jQuery("#password", $$DW).val();
                var passwordAgain = jQuery("#passwordAgain", $$DW).val();
                var validCode = jQuery("#validCode", $$DW).val();
                jQuery.ajax({
                    type: "POST",
                    url: "registerByIdCard.do",
                    dataType: "json",
                    async: false,
                    data: {"idCard": idcard, "phone": phone, "password": password, "passwordAgain": passwordAgain, "validCode": validCode},
                    cache: false,
                    success: function (data, status) {
                        if (data.code > 0) {
                            window.location.href = "turnToUserLogin.do?idcard=" + idcard;
                            d.close();
                        } else {
                            Dialog.alert(data.text);
                        }
                    }
                });
            } else {
                d.innerWin.encrypt();

                var idcard = jQuery("#idcard", $$DW).val();
                var password = jQuery("#password", $$DW).val();
                var validCode = jQuery("#validCode", $$DW).val();

                var sendobi = {"idCard": idcard, "password": password, "validCode": validCode};
                jQuery.ajax({
                    type: "POST",
                    url: "loginByIdCard.do",
                    dataType: "json",
                    async: false,
                    data: sendobi,
                    cache: false,
                    success: function (data, status) {
                        if (data.code > 0) {
                            window.location.href = "turnToUserLogin.do?idcard=" + idcard;
                            d.close();
                        } else {
                            Dialog.alert(data.text);
                        }
                    }
                });
            }
        };
        d.onLoad = function () {
            var $$DW1 = jQuery(d.innerWin.document);
            jQuery("#newpwd", $$DW1).focus();
            //$DW.$("oldpwd").focus();
        };
        d.show();
    }
}
function updateUserLoginByIdCard() {
    if (window.zDialog) {
        var diag = new zDialog({
            Widht: 250,
            Height: 400,
            URL: "showUserLoginByIdCard.do?option=update"
        });

        diag.MessageTitle = "修改密码";
        diag.Message = "修改密码";
        diag.OKEvent = function () {
            //if (diag.innerWin.Verify.hasError())
            //	return;
            var dc = diag.innerWin.Form.getData("userLoginByIdCard");
            var ajax = new Ajax("updateLoginByIdCard.do", function (data) {
                if (data) {
                    if (data.code > 0) {
                        Dialog.alert(data.text);
                        $D.close();
                    } else {
                        Dialog.alert(data.text);
                    }
                }
            });
            ajax.add(dc);
            ajax.submit();
        };
        diag.OnLoad = function () {
            //diag.innerWin.$("oldpwd").focus();
        };
        diag.show();
    } else if (window.Dialog) {
        var d = new Dialog("changepwd");
        d.Widht = 250;
        d.Height = 400;
        d.Title = "修改密码";
        d.URL = "showUserLoginByIdCard.do?option=update";
        d.OKEvent = function () {
            var $$DW = jQuery(d.innerWin.document);
            var idcard = jQuery("#idcard", $$DW).val();
            var password = jQuery("#password", $$DW).val();
            var newpassword = jQuery("#newpassword", $$DW).val();
            var newpasswords = jQuery("#newpasswords", $$DW).val();

            var sendobi = {
                "idCard": idcard,
                "password": password,
                "newpassword": newpassword,
                "newpasswords": newpasswords
            };
            jQuery.ajax({
                type: "POST",
                url: "updateLoginByIdCard.do",
                dataType: "json",
                async: false,
                data: sendobi,
                cache: false,
                success: function (data, status) {
                    if (data.code > 0) {
                        Dialog.alert(data.text);
                        d.close();
                    } else {
                        Dialog.alert(data.text);
                    }
                }
            });
        };
        d.onLoad = function () {
            var $$DW1 = jQuery(d.innerWin.document);
            jQuery("#newpwd", $$DW1).focus();
            //$DW.$("oldpwd").focus();
        };
        d.show();
    }
}

function xzCanBmCheck() {
    var isInGdq = getGdqksrq();
    if (isInGdq) {
        jQuery('input[name="bmlx"][value="1"]').attr("checked", true);
        jQuery('label[for="tp1"]').css("display", "none");
    }
}

//绑定代码 作业种类(有过滤外网不能报的数据)
dwbm_bindselectzyzl_webOld= function(id, value,ishk,bmlb, zyxms) {
    if (ishk == null || ishk == "") {
        ishk = '0';
    }
    var bf = "bmfs" in window ? bmfs : '0';
    var jg = bf == '2' ? jgdm : dwbm_jgdm;
    var lb = bf == '2' ? '9001' : dwbm_jglb;
    var bindobject = jQuery("#" + id);
    var ajax = new Ajax(Server.ContextPath + "dwbm_queryzyzlbyjg_webOld.do?jgdm=" + jg + "&jglb=" + lb + "&zyxms=" + (zyxms ? zyxms : ""), function (data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption([{
                value: "",
                name: "--请选择--"
            }], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("ishk", ishk);
    if (bmlb) {
        ajax.add("bmlb", bmlb);
    }
    ajax.setAsync(false);
    ajax.submit();
};

//绑定代码 作业项目(有过滤外网不能报的数据)
dwbm_bindselectzyxm_webOld= function(id, zyzlval,value,bmlb, zyxms) {
    var bindobject = jQuery("#" + id);
    var bf = "bmfs" in window ? bmfs : '0';
    var jg = bf == '2' ? jgdm : dwbm_jgdm;
    var lb = bf == '2' ? '9001' : dwbm_jglb;
    var ajax = new Ajax(Server.ContextPath + "dwbm_queryzyxmbyjg_webOld.do?jgdm=" + jg + "&jglb=" + lb + "&zyxms=" + (zyxms ? zyxms : ''), function (data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption([{
                value: "",
                name: "--请选择--"
            }], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("zyzl", zyzlval);
    if (bmlb) {
        ajax.add("bmlb", bmlb);
    }
    ajax.setAsync(false);
    ajax.submit();
};

// 新证外网报名查询作业项目方法
dwbm_bindSelectNewZyxm = function (objzyxm, objxmcode, value, bmlb, zyxms) {
    var bindobject = jQuery("#" + objzyxm);
    var bindobject2 = jQuery("#" + objxmcode);
    bindobject.empty();
    bindobject.removeOption(/./);
    bindobject.append("<option value=''>--请选择--</option>");
    if (bindobject2.is("select")) {
        bindobject2.empty();
        bindobject2.removeOption(/./);
        bindobject2.append("<option value=''>--请选择--</option>");
    }
    var planid = "";
    if (typeof dwbm_planid != "undefined" && dwbm_planid != null) {
        planid = dwbm_planid;
    }
    var pxjgdm = "";
    var jglb = "";
    var jgdm = "";
    if (typeof dwbm_jglb != "undefined" && dwbm_jglb != null) {
        if ("9003" == dwbm_jglb) {
            pxjgdm = dwbm_jgdm;

			jglb = dwbm_jglb;
			jgdm=ksjg_dm;//考试机构代码

		} else {
            jglb = dwbm_jglb;
            jgdm = dwbm_jgdm;
        }
    }
    var bmparam = "&jglb=" + jglb + "&jgdm=" + jgdm + "&pxjgdm=" + pxjgdm + "&zyxms=" + (zyxms ? zyxms : '') + "&sfdw=1";
    var ajax = new Ajax(Server.ContextPath + "queryNewZyxmByJg.do?v=1.1" + bmparam, function (data) {
        if (data) {
            var xm_value = '';
            for (var m = 0; m < data.length; m++) {
                var xmid = data[m].XMID;
                var xmmc = data[m].XMMC;
                var xmvalue = data[m].VALUE;
                var hmt = "<option value='" + xmid + "' xmvalue='" + xmvalue + "'>" + xmmc + "</option>";
                var hmt2 = "<option value='" + xmid + "'>" + xmvalue + "</option>";
                bindobject.append(hmt);
                if (bindobject2.is("select")) {
                    bindobject2.append(hmt2);
                }
                if (xmid == value) {
                    xm_value = xmvalue;
                }
            }
            bindobject.val(value);
            if (bindobject2.is("select")) {
                bindobject2.val(value);
            } else {
                bindobject2.val(xm_value);
            }
        }
    });
    if (bmlb != null) {
        ajax.add("bmlb", bmlb);
    }
    ajax.add("planid", planid);
    ajax.setAsync(true);
    ajax.submit();
};

// 新证外网报名查询作业项目方法
dwbm_bindSelectNewZyxmFzjgbm = function (objzyxm, objxmcode, value, bmlb) {
    var bindobject = jQuery("#" + objzyxm);
    var bindobject2 = jQuery("#" + objxmcode);
    bindobject.empty();
    bindobject.removeOption(/./);
    bindobject2.empty();
    bindobject2.removeOption(/./);
    bindobject.append("<option value=''>--请选择--</option>");
    bindobject2.append("<option value=''>--请选择--</option>");
    var jglb = "";
    var jgdm = "";
    var enjgdm = "";
    if (dwbm_ksjg_dm != null && dwbm_ksjg_dm != "") {
        jglb = "9001";
        jgdm = dwbm_ksjg_dm;
        enjgdm = dwbm_jgdm;
    } else {
        jglb = dwbm_jglb;
        jgdm = dwbm_jgdm;
    }
    var bmparam = "&jglb=" + jglb + "&jgdm=" + jgdm + "&enjgdm=" + enjgdm + "&sfdw=1";
    var ajax = new Ajax(Server.ContextPath + "queryNewZyxmByJg.do?v=1.1" + bmparam, function (data) {
        if (data) {
            for (var m = 0; m < data.length; m++) {
                var xmid = data[m].XMID;
                var xmmc = data[m].XMMC;
                var xmvalue = data[m].VALUE;
                var hmt = "<option value='" + xmid + "' xmvalue='" + xmvalue + "'>" + xmmc + "</option>";
                var hmt2 = "<option value='" + xmid + "'>" + xmvalue + "</option>";
                bindobject.append(hmt);
                bindobject2.append(hmt2);
            }
            bindobject.val(value);
            bindobject2.val(value);
        }
    });
    ajax.setAsync(true);
    ajax.submit();
};

// 新证外网报名查询作业项目方法
dwbm_bindSelectNewZyxmFzjgbmYn = function (objzyxm, objxmcode, value, bmlb) {
    var bindobject = jQuery("#" + objzyxm);
    var bindobject2 = jQuery("#" + objxmcode);
    bindobject.empty();
    bindobject.removeOption(/./);
    bindobject2.empty();
    bindobject2.removeOption(/./);
    bindobject.append("<option value=''>--请选择--</option>");
    bindobject2.append("<option value=''>--请选择--</option>");
    var jglb = "";
    var jgdm = "";
    if (dwbm_ksjg_dm != null && dwbm_ksjg_dm != "") {
        jglb = "9001";
        jgdm = dwbm_ksjg_dm;
    } else {
        jglb = dwbm_jglb;
        jgdm = dwbm_jgdm;
    }
    var bmparam = "&jglb=" + jglb + "&jgdm=" + jgdm + "&fzjgdm=" + dwbm_jgdm;
    var ajax = new Ajax(Server.ContextPath + "queryNewZyxmByJgYn.do?v=1.1" + bmparam, function (data) {
        console.log(data);
        if (data) {
            for (var m = 0; m < data.length; m++) {
                var xmid = data[m].XMID;
                var xmmc = data[m].XMMC;
                var xmvalue = data[m].VALUE;
                var hmt = "<option value='" + xmid + "' xmvalue='" + xmvalue + "'>" + xmmc + "</option>";
                var hmt2 = "<option value='" + xmid + "'>" + xmvalue + "</option>";
                bindobject.append(hmt);
                bindobject2.append(hmt2);
            }
            bindobject.val(value);
            bindobject2.val(value);
        }
    });
    ajax.setAsync(true);
    ajax.submit();
};

/**
 * 6.1 前 查询机构老项目权限
 * 6.1 后 查询机构新项目权限 + 老项目权限
 */
dwbm_bindSelectZyxmIncludeOld = function (id, zyzlval, ksjgval, value, status) {
    var bmparam = "&jgdm=" + dwbm_jgdm + "&jglb=" + dwbm_jglb;
    var bindobject = jQuery("#" + id);
    var ajax = new Ajax(Server.ContextPath + "dwbm_listZyxmByJG.do?v=1.1" + bmparam, function (data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption([{
                value: "",
                name: "--请选择--"
            }], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("zyzl", zyzlval);
    ajax.add("ksjg", ksjgval);
    ajax.setAsync(false);
    ajax.submit();
};

/**
 * 浙江发证机构报名可以选择考场信息
 */
dwbm_bindSelectKcInfo = function (id, jgdm, value, status) {
	var bmparam = '&jgdm=' + jgdm;
	var bindobject = jQuery('#' + id);
	var ajax = new Ajax(Server.ContextPath + 'dwbm_listKcInfomByJG.do?v=1.1' + bmparam, function (data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption([{
				value: '',
				name: '--请选择--'
			}], false, false, 'value', 'name');
			bindobject.addOption(data, false, false, 'value', 'name');
			bindobject.val(value);
		}
	});
	ajax.setAsync(false);
	ajax.submit();
};

// 浙江发证机构报名, 根据考场信息加载项目
dwbm_bindSelectZyXmByKcInfo = function (id, codeId, kcid, ishj, value, status) {
	ishj = ishj || 0;
	var param = '&kcid=' + kcid+'&isHj='+ishj;
	var obj = jQuery('#' + id);
	var codeObj = jQuery('#' + codeId);
	var ajax = new Ajax(Server.ContextPath + 'dwbm_listZyxmByKcInfo.do?v=1.1' + param, function (data) {
		if (data) {
			obj.empty();
			obj.removeOption(/./);
			codeObj.empty();
			codeObj.removeOption(/./);
			for (var i = 0; i < data.length; i++) {
				var o = data[i];
				obj.append("<option value='" + o.ID + "' xmvalue='" + o.VALUE + "'>" + o.XMMC + "</option>");
				codeObj.append("<option value='" + o.ID + "'>" + o.VALUE + "</option>");
			}
			obj.val(value);
			codeObj.val(value);
		}
	});
	ajax.setAsync(false);
	ajax.submit();
};

dwbm_queryHjffByKcInfo = function (id, defaultvalue, kcid, value, status) {
	var bindobject = jQuery("#" + id);
	var objStr = "";
	if (defaultvalue == null || defaultvalue == '') {
		var ajax = new Ajax(Server.ContextPath + "dwbm_listHjffByKcInfo.do", function (data) {
			if (data) {
				bindobject.empty();
				for (var i = 0; i < data.length; i++) {
					objStr = objStr + "<li><input type='checkbox' id='hjff1' name='hjff1' value='" + data[i].value + "' onchange='checkValue(this,\"hjff\")' />" + data[i].name + "</li>";
				}
			}
		});
		ajax.add('kcid', kcid);
		ajax.setAsync(false);
		ajax.submit();
	} else {
		jQuery("#hjff").val("," + defaultvalue);
		var defaultHjff = defaultvalue.split(",");
		var ajax = new Ajax(Server.ContextPath + "dwbm_listHjffByKcInfo.do", function (data) {
			if (data) {
				bindobject.empty();
				for (var i = 0; i < data.length; i++) {
					var checkhjff = false;
					for (var j = 0; j < defaultHjff.length; j++) {
						if (defaultHjff[j] == data[i].value) {
							checkhjff = true;
						}
					}
					if (checkhjff) {
						objStr = objStr + "<li><input type='checkbox' id='hjff1' name='hjff1' checked='checked'  value='" + data[i].value + "' onchange='checkValue(this,\"hjff\")' />" + data[i].name + "</li>";
					} else {
						objStr = objStr + "<li><input type='checkbox' id='hjff1' name='hjff1' value='" + data[i].value + "' onchange='checkValue(this,\"hjff\")' />" + data[i].name + "</li>";
					}
				}
			}
		});
		ajax.add('kcid', kcid);
		ajax.setAsync(false);
		ajax.submit();
	}
	if (objStr == null || objStr == '') {
		bindobject.prepend("<ul>该考场没有焊接方法的考试权限</ul>")
	} else {
		bindobject.prepend("<ul>" + objStr + "</ul>");
	}
};

dwbm_queryHjJscldlByKcInfo = function (id, defaultvalue, kcid, value, status) {
	var bindobject = jQuery("#" + id);
	var objStr = "";
	if (defaultvalue == null || defaultvalue == '') {
		var ajax = new Ajax(Server.ContextPath + "dwbm_listJscllbByKcInfo.do", function (data) {
			if (data) {
				bindobject.empty();
				for (var i = 0; i < data.length; i++) {
					objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' value='" + data[i].value + "' />" + data[i].name + "</li>";
				}
			}
		});
		ajax.add('kcid', kcid);
		ajax.setAsync(false);
		ajax.submit();
	} else {
		var defaultHjff = defaultvalue.split(",");
		var ajax = new Ajax(Server.ContextPath + "dwbm_listJscllbByKcInfo.do", function (data) {
			if (data) {
				bindobject.empty();
				for (var i = 0; i < data.length; i++) {
					var checkhjff = false;
					for (var j = 0; j < defaultHjff.length; j++) {
						if (defaultHjff[j] == data[i].value) {
							checkhjff = true;
						}
					}
					if (checkhjff) {
						objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' checked='checked'  value='" + data[i].value + "' />" + data[i].name + "</li>";
					} else {
						objStr = objStr + "<li><input type='radio' id='jscllb' name='jscllb' value='" + data[i].value + "' />" + data[i].name + "</li>";
					}
				}
			}
		});
		ajax.add('kcid', kcid);
		ajax.setAsync(false);
		ajax.submit();
	}
	if (objStr == null || objStr == '') {
		bindobject.prepend("<ul>该考场没有母材种类的考试权限</ul>")
	} else {
		bindobject.prepend("<ul>" + objStr + "</ul>");
	}
};

// 新证外网报名查询作业项目方法(广东)
dwbm_bindSelectNewZyxmFzjgbmGd = function (objzyxm, objxmcode, value, bmlb,fzjgdm) {

    var bindobject=jQuery("#" + objzyxm);
	var bindobject2 = jQuery("#" + objxmcode);
	bindobject.empty();
	bindobject.removeOption(/./);
	bindobject2.empty();
	bindobject2.removeOption(/./);
	bindobject.append("<option value=''>--请选择--</option>");
	bindobject2.append("<option value=''>--请选择--</option>");
	var jglb = "9002";
	var jgdm = fzjgdm;

    var bmparam = "&bmlb="+bmlb+"&jglb="+jglb+"&jgdm="+jgdm;
	var ajax = new Ajax(Server.ContextPath + "queryNewZyxmByJgGd.do?v=1.1" + bmparam, function (data) {
		if (data) {
			for (var m = 0; m < data.length; m++) {
				var xmid = data[m].XMID;
				var xmmc = data[m].XMMC;
				var xmvalue = data[m].VALUE;
				var hmt = "<option value='" + xmid + "' xmvalue='" + xmvalue + "'>" + xmmc + "</option>";
				var hmt2 = "<option value='" + xmid + "'>" + xmvalue + "</option>";
				bindobject.append(hmt);
				bindobject2.append(hmt2);
			}
			bindobject.val(value);
			bindobject2.val(value);
		}
	});
	ajax.setAsync(true);
	ajax.submit();
};
/**
 * 根据发证机构和项目获取考试机构信息（广东）
 * @param objksjg
 * @param bmlb
 * @param fzjgdm
 */
dwbm_bindSelectKsjgByFzjgAndXmGd = function (objksjg,bmlb,fzjgdm,zyxm,ssdq) {

    var bindobject = jQuery("#" + objksjg);
	bindobject.empty();
	bindobject.removeOption(/./);

	bindobject.append("<option value=''>--请选择--</option>");

	var jglb = "9002";
	var jgdm = fzjgdm;

	var bmparam = encodeURI("&bmlb="+bmlb+"&jgdm="+jgdm+"&zyxm="+zyxm+"&ssdq="+ssdq);
	var ajax = new Ajax(Server.ContextPath + "queryKsjgByFzjgXm.do?v=1.1" + bmparam, function (data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			bindobject.addOption([{
				value: '',
				name: '--请选择--'
			}], false, false, 'value', 'name');
			bindobject.addOption(data, false, false, 'value', 'name');
			//bindobject.val(value);
		}
	});
	ajax.setAsync(true);
	ajax.submit();
};

function showCertInfo(vals) {
	if (vals != null && vals != "") {
		var splits = vals.split("#");
		if (splits.length == 2) {
			//查看作业项目是否为老项目
			jQuery.get("isOldZyxm.do?zyxm=" + splits[1], function (data) {
				if (data != null && data != "") {
					if (data.ISNEW == 0 && (data.NEW_ID == "" || data.NEW_ID == null)) {
						jQuery("#tzsbzl").val("");
						jQuery("#zyxm").html("");
                        jQuery("#zyxm").attr("disabled", true);
						jQuery("#zyxm_val").val("");
						jQuery("#zyxm").attr("title", "");
						alert("选择的原有项目是已被取消的项目");
					} else {
						jQuery("#zyxm").attr("title", "");
						if (splits[1] == "0202" || splits[1] == "0203") {
							alert("原一级锅炉司炉变更为工业锅炉司炉；原二、三级锅炉司炉依据持证人申请或实际操作锅炉情况，变更为工业锅炉司炉或电站锅炉司炉");
						}
						if (splits[1] == "0802" || splits[1] == "0805" || splits[1] == "0806" || splits[1] == "0807" || splits[1] == "0808" || splits[1] == "0809"
							|| splits[1] == "0810" || splits[1] == "0811") {
							alert("直接换发。原客运索道维修(限电气维修)项目依据持证人申请可以同时换发客运索道修理、客运索道司机两个项目");
						}
						if (splits[1] == "0904") {
							alert("直接换发。水上大型游乐设施操作与维修项目依据持证人申请可以同时换发大型游乐设施修理、操作两个项目");
						}
						jQuery("#tzsbzl").val(splits[1]);
						jQuery("#zyzl").val(splits[0]);
						jQuery("#zyzl").attr("disabled", true);
						var zyxmdm = "";
						if (data.ISNEW == 2) {
							zyxmdm = splits[1];
						} else {
							zyxmdm = data.NEW_ID;
						}

						if (splits[1] != '0802' && splits[1] != '0805' && splits[1] != '0806'
							&& splits[1] != '0807' && splits[1] != '0808' && splits[1] != '0809' && splits[1] != '0810'
							&& splits[1] != '0811' && splits[1] != '0904' && splits[1] != '0202' && splits[1] != '0203' && splits[1] != '0704' && splits[1] != '0792') {
							bindselectzyxm('zyxm', splits[0], zyxmdm, 1);
                            jQuery("#zyxm").attr("disabled", true);
						} else {
							bindselectzyxm('zyxm', splits[0], splits[1], 1);
							jQuery("#zyxm").removeAttr("disabled");
						}
					}
				}
			})
		} else {
			//查看作业项目是否为老项目
			jQuery.get("isOldZyxm.do?zyxm=" + splits[5], function (data) {
				if (data != null && data != "") {
					if (data.ISNEW == 0 && (data.NEW_ID == "" || data.NEW_ID == null)) {
						jQuery("#tzsbzl").val("");
						jQuery("#zyxm").html("");
                        jQuery("#zyxm").attr("disabled", true);
						jQuery("#zyxm_val").val("");
						jQuery("#zyxm").attr("title", "");
						alert("选择的原有项目是已被取消的项目");
					} else {
						jQuery("#zyxm").attr("title", "");
						if (splits[5] == "0202" || splits[5] == "0203") {
							alert("原一级锅炉司炉变更为工业锅炉司炉；原二、三级锅炉司炉依据持证人申请或实际操作锅炉情况，变更为工业锅炉司炉或电站锅炉司炉");
						}
						if (splits[5] == "0802" || splits[5] == "0805" || splits[5] == "0806" || splits[5] == "0807" || splits[5] == "0808" || splits[5] == "0809"
							|| splits[5] == "0810" || splits[5] == "0811") {
							alert("直接换发。原客运索道维修(限电气维修)项目依据持证人申请可以同时换发客运索道修理、客运索道司机两个项目");
						}
						if (splits[5] == "0904") {
							alert("直接换发。水上大型游乐设施操作与维修项目依据持证人申请可以同时换发大型游乐设施修理、操作两个项目");
						}
						if (jQuery("#sqrxm").length > 0) {
							jQuery("#sqrxm").val(splits[0]);
						}
						if (jQuery("#zsbh").length > 0) {
							jQuery("#zsbh").val(splits[1]);
						}
						if (jQuery("#bak4").length > 0) {
							jQuery("#bak4").val(splits[2]);
						}
						if (jQuery("#fzrq").length > 0) {
                            timeMethod = 'yyyy-MM-dd';
                            document.getElementById("model").value = "切换到月";
							jQuery("#fzrq").val(splits[3]);
						}
						if (jQuery("#zyzl").length > 0 && splits[4] != null && splits[4] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
							jQuery("#zyzl").val(splits[4]);
						}
						jQuery("#zyzl").attr("disabled", true);
						if (jQuery("#zyxm").length > 0 && splits[5] != null && splits[5] != "" && jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
							jQuery("#tzsbzl").val(splits[5]);
							if (jQuery("#zyzl option[value='" + splits[4] + "']").length > 0) {
								if (splits[5] != '0802' && splits[5] != '0805' && splits[5] != '0806'
									&& splits[5] != '0807' && splits[5] != '0808' && splits[5] != '0809' && splits[5] != '0810'
									&& splits[5] != '0811' && splits[5] != '0904' && splits[5] != '0202' && splits[5] != '0203' && splits[5] != '0704' && splits[5] != '0792') {
                                    jQuery("#zyxm").attr("disabled", true);
									if (splits[8] != null && splits[8] != "") {
										bindselectzyxm('zyxm', splits[4], splits[8], 1);
									} else {
										bindselectzyxm('zyxm', splits[4], splits[5], 1);
									}
								} else {
									bindselectzyxm('zyxm', splits[4], splits[5], 1);
									jQuery("#zyxm").removeAttr("disabled");
								}
							} else {
								bindselectzyxm('zyxm', splits[4], splits[5], 1);
							}
						} else {
							jQuery("#zyxm").val("");
							jQuery("#zyxm_val").val("");
						}
						if (jQuery("#oldzyxm").length > 0) {
							jQuery("#oldzyxm").val(splits[6]);
						}
					}
				}
			})
			//判断是否可以修改证书数据
			// if(splits[7]!= null && splits[7]=="0"){
			//     jQuery("#sfzh").attr("disabled",true);
			//     jQuery("#zsbh").attr("disabled",true);
			//     jQuery("#fzrq").attr("disabled",true);
			//     jQuery("#bak4").attr("disabled",true);
			// }
		}
	}
}


//绑定代码 作业项目
bindselectzyxm= function(id, zyzlval,value,bmlb, status) {

	var bindobject = jQuery("#" + id);
	var bmid = jQuery("#bmid").val();
	var bmparam = bmid ? ("&bmid=" + bmid) : "";
	var url="";
	try {
		url = "dwbmqueryzyxmbyjg.do?v=1.1"+bmparam + "&zyxm="+value+ "&yxzt="+yxzt+ "&jgdm=" + dwbm_jgdm + "&jglb=" + dwbm_jglb;
	}catch (e) {
		url = "dwbmqueryzyxmbyjg.do?v=1.1"+bmparam + "&zyxm="+value+ "&jgdm=" + dwbm_jgdm + "&jglb=" + dwbm_jglb;
	}
	var ajax = new Ajax(Server.ContextPath+url, function(data) {
		if (data) {
			bindobject.empty();
			bindobject.removeOption(/./);
			if(value!='0802'&&value!='0805'&&value!='0806'
				&&value!='0807'&&value!='0808'&&value!='0809'&&value!='0810'
				&& value != '0811' && value != '0904' && value != '0202' && value != '0203' && value != '0704' && value != '0792') {
				bindobject.addOption( [ {
					value : "",
					name : "--请选择--"
				} ], false, false, "value", "name");
			}
			bindobject.addOption(data, false, false, "value", "name");
			if(value!='0802'&&value!='0805'&&value!='0806'
				&&value!='0807'&&value!='0808'&&value!='0809'&&value!='0810'
				&& value != '0811' && value != '0904' && value != '0202' && value != '0203' && value != '0704' && value != '0792') {
				bindobject.val(value);
			}
			if(value=="0904"){
				bindobject.val("0996");
			}
			if (value == "0704" || value == "0792") {
				bindobject.val("0798");
			}
			if(value!=null&&value!=""){
				var xm = jQuery("#zyxm").find("option:selected").text();
				if(xm!=null && xm!=""){
					var xms = xm.split(",");
					var xmdh="";
					for(var i=0;i<xms.length;i++){
						var dh = xms[i].substr(xms[i].indexOf("[")+1,xms[i].indexOf("]")-xms[i].indexOf("[")-1);
						if(i==0){
							xmdh = dh;
						}else{
							xmdh = xmdh +","+ dh;
						}
					}
					jQuery("#zyxm_val").val(xmdh);
				}
			}
		}
	});
	ajax.add("zyzl", zyzlval);
	if(bmlb != null){
		ajax.add("bmlb",bmlb);
	}
	var pxjgdm = "";
	try {
		if(px_jgdm != undefined && px_jgdm != null){
			pxjgdm = px_jgdm;
		}
	}catch (e) {
		pxjgdm = "";
	}
	ajax.add("pxjgdm",pxjgdm);
	ajax.setAsync(true);
	ajax.submit();
};

//绑定代码 作业项目
bindselectzyzl= function(id, zyzlval,value,bmlb, status) {

    var bindobject = jQuery("#" + id);
    var ajax = new Ajax(Server.ContextPath+"queryzyzl.do", function(data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption( [ {
                value : "",
                name : "--请选择--"
            } ], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("zyzl", zyzlval);
    if(bmlb != null){
        ajax.add("bmlb",bmlb);
    }
    ajax.setAsync(true);
    ajax.submit();
};

//绑定代码 作业项目
bindselectzyxmSx= function(id, zyzlval,value,bmlb, status) {

    var bindobject = jQuery("#" + id);
    var ajax = new Ajax(Server.ContextPath+"queryzyxm.do", function(data) {
        if (data) {
            bindobject.empty();
            bindobject.removeOption(/./);
            bindobject.addOption( [ {
                value : "",
                name : "--请选择--"
            } ], false, false, "value", "name");
            bindobject.addOption(data, false, false, "value", "name");
            bindobject.val(value);
        }
    });
    ajax.add("zyzl", zyzlval);
    if(bmlb != null){
        ajax.add("bmlb",bmlb);
    }
    ajax.setAsync(true);
    ajax.submit();
};
