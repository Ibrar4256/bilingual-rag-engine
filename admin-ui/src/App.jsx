import { useState } from "react";
import { isLoggedIn } from "./api.js";
import LoginPage from "./pages/LoginPage.jsx";
import Dashboard from "./pages/Dashboard.jsx";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());

  if (!loggedIn) {
    return <LoginPage onLogin={() => setLoggedIn(true)} />;
  }

  return <Dashboard />;
}
