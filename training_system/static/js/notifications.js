/**
 * 高级通知系统 (Toast & Modal)
 * 供管理后台统一调用，旨在取代原生的 alert() 和 confirm()。
 */

(function() {
    // 确保全局容器存在
    function ensureToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * 显示吐司通知。
     * @param {string} message - 消息内容
     * @param {string} type - 'success', 'error', 'warning', 'info'
     */
    window.showToast = function(message, type = 'info') {
        const container = ensureToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || 'ℹ'}</div>
            <div class="toast-content">${message}</div>
        `;

        container.appendChild(toast);

        // 自动移除
        setTimeout(() => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        }, 4500);
    };

    /**
     * 显示自定义确认模态框。
     * @param {string} title - 标题
     * @param {string} message - 消息内容 (支持 HTML)
     * @param {string} confirmText - 确认按钮文本
     * @param {string} type - 'primary' 或 'danger'
     * @returns {Promise<boolean>}
     */
    window.showConfirm = function(title, message, confirmText = '确认', type = 'primary') {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            
            const btnClass = type === 'danger' ? 'modal-btn-danger' : 'modal-btn-confirm';
            
            overlay.innerHTML = `
                <div class="modal-container">
                    <div class="modal-header">
                        <h3>${title}</h3>
                    </div>
                    <div class="modal-body">
                        ${message}
                    </div>
                    <div class="modal-footer">
                        <button class="modal-btn modal-btn-cancel">取消</button>
                        <button class="modal-btn ${btnClass}">${confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);
            // 强制回流以触发动画
            overlay.offsetHeight;
            overlay.classList.add('active');

            const cleanup = (result) => {
                overlay.classList.remove('active');
                setTimeout(() => {
                    overlay.remove();
                    resolve(result);
                }, 300);
            };

            overlay.querySelector('.modal-btn-cancel').onclick = () => cleanup(false);
            overlay.querySelector(`.${btnClass}`).onclick = () => cleanup(true);
        });
    };

    /**
     * 兼容性封装
     */
    window.showMessage = function(msg, type = 'info') {
        window.showToast(msg, type);
    };
})();
