import { createContext, useCallback, useContext, useEffect, useState } from 'react';

/**
 * Router tối giản cho 3 màn của app (trang khách, 2 tab CRM).
 *
 * VÌ SAO TỰ VIẾT thay vì react-router: cả app chỉ có 3 đường dẫn tĩnh, không có
 * tham số động, không có route lồng nhau. Thêm một dependency 20KB cho ngần ấy
 * là không đáng.
 *
 * VÌ SAO CẦN CÓ: trước đây mỗi tab là một `<a href>` thật, đổi tab là trình
 * duyệt tải lại toàn bộ trang (~3MB JS). Lý do lúc đó là `<CopilotKit>` chọn
 * agent theo `window.location.pathname` và chỉ đọc một lần khi mount. Bây giờ
 * `path` nằm trong state React, `main.jsx` đọc nó để chọn agent, nên đổi tab chỉ
 * cần render lại — không còn round-trip mạng nào.
 */
const NavigationContext = createContext(null);

export function NavigationProvider({ children }) {
  const [path, set_path] = useState(() => window.location.pathname);

  const navigate = useCallback((next) => {
    if (!next || next === window.location.pathname) return;
    window.history.pushState({}, '', next);
    set_path(next);
  }, []);

  // Nút back/forward của trình duyệt đổi URL mà KHÔNG bắn sự kiện nào khác —
  // thiếu listener này thì URL lùi lại còn giao diện đứng nguyên ở tab cũ.
  useEffect(() => {
    const on_pop = () => set_path(window.location.pathname);
    window.addEventListener('popstate', on_pop);
    return () => window.removeEventListener('popstate', on_pop);
  }, []);

  return (
    <NavigationContext.Provider value={{ path, navigate }}>{children}</NavigationContext.Provider>
  );
}

export function useNavigation() {
  const value = useContext(NavigationContext);
  if (!value) throw new Error('useNavigation phải nằm trong <NavigationProvider>.');
  return value;
}

/**
 * Handler cho thẻ `<a>` điều hướng nội bộ.
 *
 * Vẫn giữ `href` thật trên thẻ `<a>`: người dùng cần rê chuột thấy đích đến,
 * và Ctrl/Cmd+click hay chuột giữa phải mở được tab mới như mọi link khác —
 * nên những trường hợp đó KHÔNG được chặn `preventDefault`.
 */
export function link_handler(navigate, path) {
  return (event) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    event.preventDefault();
    navigate(path);
  };
}
