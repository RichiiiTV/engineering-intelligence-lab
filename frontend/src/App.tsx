import AdvancedApp from "./AdvancedApp";
import UserApp from "./UserApp";
import SiemensHelp from "./SiemensHelp";

export default function App() {
  const params = new URLSearchParams(location.search);
  return params.get("view") === "advanced" &&
    params.get("page") === "siemens" ? (
    <SiemensHelp />
  ) : params.get("view") === "advanced" ? (
    <AdvancedApp />
  ) : (
    <UserApp />
  );
}
