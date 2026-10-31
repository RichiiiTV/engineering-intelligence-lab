import AdvancedApp from "./AdvancedApp";
import UserApp from "./UserApp";
import SiemensHelp from "./SiemensHelp";
import MachineApp from "./MachineApp";
import ChatApp from "./ChatApp";
import AdminWorkspace from "./AdminWorkspace";
import { useCurrentUser } from "./AuthGate";

export default function App() {
  const params = new URLSearchParams(location.search);
  const user = useCurrentUser();
  if (user?.role !== "admin") return <ChatApp />;
  if (params.get("page") === "machines" && params.get("view") !== "advanced")
    return (
      <AdminWorkspace
        currentUserId={user.id}
        onClose={() => location.assign("/")}
      />
    );
  return params.get("page") === "machines" ? (
    <MachineApp />
  ) : params.get("view") === "advanced" && params.get("page") === "siemens" ? (
    <SiemensHelp />
  ) : params.get("view") === "advanced" ? (
    <AdvancedApp />
  ) : params.get("view") === "legacy" ? (
    <UserApp />
  ) : (
    <ChatApp />
  );
}
