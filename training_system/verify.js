;(function () {

    function setup($) {
        $.verifySiteX = 0;
        $.verifyResult = false;
        var defaultCss = {
            top: '25%',
            width: '380px',
            padding: '0px',
            'border-radius': '8px',
            'background-color': 'none',
            opacity: '1'
        };

        var mobileCss = {
            top: '15%',
            width: '380px',
            padding: '0px',
            left: 0,
            'border-radius': '8px',
            'background-color': 'none',
            opacity: '1'
        }
        $.showVerify = function (callback) {
            // if (navigator.appName == "Microsoft Internet Explorer" &&
            //     (navigator.appVersion.split(";")[1].replace(/[ ]/g, "") == "MSIE8.0" ||
            //         navigator.appVersion.split(";")[1].replace(/[ ]/g, "") == "MSIE7.0")) {
            //   alert('当前浏览器版本过低，请升级浏览器（至IE9及以上，推荐IE11）或使用其它浏览器（360浏览器请使用极速模式）！');
            //   return;
            // }

            var windowWidth = typeof document.documentElement.clientWidth == 'undefined' ? window.innerWidth : document.documentElement.clientWidth;
            var windowHeight = typeof document.documentElement.clientHeight == 'undefined' ? window.innerHeight : document.documentElement.clientHeight;
            defaultCss.left = ((windowWidth - $('.verify-container').width()) / 2) + 'px';
            defaultCss.top = (((windowHeight - $('.verify-container').height()) / 2) > 200 ? 200 : ((windowHeight - $('.verify-container').height()) / 2)) + 'px';

            $.blockUI({message: $('#verify-container'), css: isMobile() ? mobileCss: defaultCss});
            initVerify();
            $("#verifySliderBtn").animate({"left": "0px"}, 200);
            $("#verifySmallImg").animate({"left": "0px"}, 200);
            /* 初始化按钮拖动事件 */
            // 鼠标点击事件
            $("#verifySliderBtn").mousedown(function () {
                // 鼠标移动事件
                var pageX = this.getBoundingClientRect().left;
                var localX = 0;
                document.onmousemove = function (ev) {
                    ev = ev ?  ev : window.event;
                    localX = ev.clientX - pageX;
                    setSlider(localX);
                };
                // 鼠标松开事件
                document.onmouseup = function () {
                    document.onmousemove = null;
                    document.onmouseup = null;
                    checkImageValidate(callback);
                };
            });

            // 手机触摸事件
            $("#verifySliderBtn").on('touchstart', function (e) {
                $('body').css('touch-action', 'none');
                var pageX = this.getBoundingClientRect().left;
                $("#verifySliderBtn").on('touchmove', function (ev) {
                    setSlider(ev.originalEvent.targetTouches[0].clientX - pageX);
                });
                $("#verifySliderBtn").on('touchend', function (ee) {
                    $('body').css('touch-action', '');
                    checkImageValidate(callback);
                    if($.verifyResult){
                        $("#verifySliderBtn").off('touchstart');
                    }
                    $("#verifySliderBtn").off('touchmove touchend');
                })

            });

            $("#verifyClose").click(function () {
                $.unblockUI();
                $.verifyResult = false;
                $("#verifySliderBtn").animate({"left": "0px"}, 200);
                $("#verifySmallImg").animate({"left": "0px"}, 200);

                if (jQuery("#verifyUuid")) {
                    jQuery("#verifyUuid").val("");
                }
            });
            $("#verifyRefresh").click(function () {
                initVerify();
            });
        };

        function initVerify() {
            $.ajax({
                async: false,
                type: "get",
                url: "../getVerify.do", ///getVerify.do
                dataType: "json",
                data: { verifyType : $('#hubeiZwfwType').val() && $('#hubeiZwfwType').val() == 'hubeiZwfw' ? 'hubeiZwfw' : '' },
                success: function (data) {
                    $("#verifyBigImg").attr("src", "data:image/png;base64," + data.oriCopyImage);
                    $("#verifySmallImg").attr("src", "data:image/png;base64," + data.newImage);

                    if (data.verifyUuid) {
                        $("#verifyUuid").val(atob(data.verifyUuid));
                    }
                }
            });
        }

        function checkImageValidate(callback) {
            $.ajax({
                async: false,
                type: "POST",
                url: "../validateVerify.do",///validateVerify.do
                dataType: "json",
                data: {
                    siteX: $.verifySiteX,
                    verifyType : $('#hubeiZwfwType').val() && $('#hubeiZwfwType').val() == 'hubeiZwfw' ? 'hubeiZwfw' : '',
                    verifyUuid: $("#verifyUuid").val()
                },
                success: function (data) {
                    if (data.code == 1) {
                        $.verifyResult = true;
                        $.unblockUI();
                        if (typeof callback == "function") {
                            callback($.verifySiteX);
                        }
                    } else {
                        alert(data.text);
                        $.verifyResult = false;
                        // 验证未通过，将按钮和拼图恢复至原位置
                        $("#verifySliderBtn").animate({"left": "0px"}, 200);
                        $("#verifySmallImg").animate({"left": "0px"}, 200);
                    }
                }
            });
        }

        function setSlider(localX) {
            if (localX >= 0 && localX <= (550-50)) {
                $("#verifySliderBtn").css("left", (localX) + "px");
                $("#verifySmallImg").css("left", (localX) + "px");
                $.verifySiteX = localX;
            }
        }

        function isMobile() {
            if(/Android|webOS|iPhone|iPod|BlackBerry/i.test(navigator.userAgent)) {
                return true;
            }
            return false;
        }

    }

    /*global define:true */
    if (typeof define === 'function' && define.amd && define.amd.jQuery) {
        define(['jquery'], setup);
    } else {
        setup(jQuery);
    }
})();