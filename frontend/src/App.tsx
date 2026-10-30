import AdvancedApp from "./AdvancedApp";
import UserApp from "./UserApp";
import SiemensHelp from "./SiemensHelp";
import MachineApp from "./MachineApp";

export default function App() {
  const params = new URLSearchParams(location.search);
  return params.get("page") === "machines" ? (
    <MachineApp />
  ) : params.get("view") === "advanced" && params.get("page") === "siemens" ? (
    <SiemensHelp />
  ) : params.get("view") === "advanced" ? (
    <AdvancedApp />
  ) : (
    <UserApp />
  );
}
