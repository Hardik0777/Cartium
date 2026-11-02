import { useSearchParams } from "react-router-dom";
import Approvals from "./admin/Approvals";
import Complaints from "./admin/Complaints";
import Overview from "./admin/Overview";
import Refunds from "./admin/Refunds";
import Users from "./admin/Users";

const TABS = [["overview", "Overview"], ["approvals", "Approvals"], ["users", "Users"], ["refunds", "Refunds"], ["complaints", "Complaints"]] as const;

export default function AdminDashboard() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "overview";
  return (
    <div className="seller">
      <h1>Admin</h1>
      <nav className="seller-tabs" role="tablist" aria-label="Admin">
        {TABS.map(([v, l]) => (
          <button key={v} role="tab" aria-selected={tab === v} className={tab === v ? "seller-tab on" : "seller-tab"} onClick={() => setParams({ tab: v })}>{l}</button>
        ))}
      </nav>
      {tab === "overview" && <Overview goTo={(t) => setParams({ tab: t })} />}
      {tab === "approvals" && <Approvals />}
      {tab === "users" && <Users />}
      {tab === "refunds" && <Refunds />}
      {tab === "complaints" && <Complaints />}
    </div>
  );
}
