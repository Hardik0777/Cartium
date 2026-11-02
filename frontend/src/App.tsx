import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Account from "./pages/Account";
import AdminDashboard from "./pages/AdminDashboard";
import Home from "./pages/Home";
import Login from "./pages/Login";
import SellerDashboard from "./pages/SellerDashboard";
import Signup from "./pages/Signup";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} />
        <Route path="/seller" element={<ProtectedRoute roles={["seller"]}><SellerDashboard /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute roles={["admin"]}><AdminDashboard /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
