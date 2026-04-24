function _showHideInfo(id){
	if(jQuery("#"+id).length > 0){
		jQuery("#"+id).focus(function (){
			jQuery("#"+id+"_info").show();//显示
		});
		jQuery("#"+id).blur(function (){
			jQuery("#"+id+"_info").hide();//隐藏
		});
	}
}
function _addInfoDiv(id,rh,th,title){
	var rights = rh || 5;
	var h = parseInt(jQuery("#"+id).height()/2);
	var tops = th + h || 250;
	if(jQuery("#"+id).length > 0){
		var appstr = "<div class=\"info\" id=\""+id+"_info\" style=\"right:"+rights+"px; top:"+tops+"px;display:none\">" +
		"<ul><li>"+title+"</li> </ul></div>";
		jQuery(document.body).append(appstr);
	}
}
//页面注册
jQuery(document).ready(function (){
	_addInfoDiv("lxdh",5,jQuery("#lxdh").length > 0?jQuery("#lxdh").offset().top:0,"说明：请填写本人真实有效的手机号。");
	_showHideInfo("lxdh");
	//单位
	//_addInfoDiv("yrdw",5,jQuery("#yrdw").length > 0?jQuery("#yrdw").offset().top:0,"备注：需要由用人单位、专业下属机构或者实习单位提供并盖章");
	//_showHideInfo("yrdw");
	_addInfoDiv("yrdw",5,jQuery("#yrdw").length > 0?jQuery("#yrdw").offset().top:0,"说明：有用人单位的填写用人单位，无用人单位的填写个人姓名。");
	_showHideInfo("yrdw");
	//工作简历
	_addInfoDiv("gzjl",5,jQuery("#gzjl").length > 0?jQuery("#gzjl").offset().top:0,"工作简历：从事所考核特种设备项目的工作经历，从事时间应达到相应特种设备考规的要求；（请按格式填写）");
	_showHideInfo("gzjl");
	//培训情况
	_addInfoDiv("pxqk",5,jQuery("#pxqk").length > 0 ?jQuery("#pxqk").offset().top:0,"培训情况：指单位内部的培训；（请按格式填写）例如：(2012-06-08)参加申请项目的培训及安全教育。");
	_showHideInfo("pxqk");
	//培训情况
	_addInfoDiv("aqpxqk",5,jQuery("#aqpxqk").length > 0 ?jQuery("#aqpxqk").offset().top:0,"培训情况：指单位内部的培训；（请按格式填写）例如：(2012-06-08)参加申请项目的培训及安全教育。");
	_showHideInfo("aqpxqk");
	//相关材料提醒
	jQuery("input[name='xgcl']").each(function (index){
		var val = this.value;
		if(val == '0701'){
			//0701
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：身份证作为证明文件，提供正反两面复印在一张A4纸上的复印件");
			_showHideInfo(this.id);
		}else if(val == '0702'){
			//0702
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：照片文件格式需是JPG格式");
			_showHideInfo(this.id);
		}else if(val == '0704'){
			//0704
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：需要由用人单位、专业下属机构或者实习单位提供并盖章");
			_showHideInfo(this.id);
		}else if(val == '0705'){
			//0705
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：需要由用人单位、专业下属机构或者实习单位提供并盖章");
			_showHideInfo(this.id);
		}else if(val == '0706'){
			//0706
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：参照所申请项目的考核大纲要求");
			_showHideInfo(this.id);
		}else if(val == '0802'){
			//0802
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：需要由用人单位或专业下属机构提供并盖章");
			_showHideInfo(this.id);
		}else if(val == '0803'){
			//0803
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：需要由用人单位提供并盖章");
			_showHideInfo(this.id);
		}else if(val == '0804'){
			//0804
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：参照所申请项目的考核大纲要求");
			_showHideInfo(this.id);
		}else if(val == '0805'){
			//0805
			_addInfoDiv(this.id,5,jQuery("#"+this.id).offset().top,"备注：由领证时（指首次复审）或者上次复审以来的用人单位出具");
			_showHideInfo(this.id);
		}
	});
});