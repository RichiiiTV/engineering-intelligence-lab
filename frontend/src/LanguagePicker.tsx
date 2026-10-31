import { setLanguage, useLanguage } from "./i18n";

export default function LanguagePicker() {
  const language = useLanguage();
  return (
    <label className="language-picker">
      <span>Sprache / Language</span>
      <select
        aria-label="Sprache / Language"
        value={language}
        onChange={(event) => setLanguage(event.target.value)}
      >
        <option value="de">Deutsch</option>
        <option value="en">English</option>
      </select>
    </label>
  );
}
