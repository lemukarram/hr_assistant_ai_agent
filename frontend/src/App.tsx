import "./i18n/config";
import { useEffect } from "react";
import { useAuthStore } from "./store/auth";
import { useLanguageStore } from "./store/language";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";

export default function App() {
  const { isAuthenticated } = useAuthStore();
  const { language } = useLanguageStore();

  useEffect(() => {
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = language;
  }, [language]);

  return isAuthenticated ? <ChatPage /> : <LoginPage />;
}
