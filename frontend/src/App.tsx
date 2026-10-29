import AdvancedApp from "./AdvancedApp";
import UserApp from "./UserApp";

export default function App() {
  return new URLSearchParams(location.search).get("view") === "advanced" ? (
    <AdvancedApp />
  ) : (
    <UserApp />
  );
}
