import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './lang/en.json';
import fa from './lang/fa.json';
import ar from './lang/ar.json';
import zhCN from './lang/zh_CN.json';
import zhTW from './lang/zh_TW.json';
import ja from './lang/ja.json';
import ru from './lang/ru.json';
import vi from './lang/vi.json';
import es from './lang/es.json';
import id from './lang/id.json';
import uk from './lang/uk.json';
import tr from './lang/tr.json';
import ptBR from './lang/pt_BR.json';

export const resources = {
  en: { translation: en }, fa: { translation: fa }, ar: { translation: ar },
  zh_CN: { translation: zhCN }, zh_TW: { translation: zhTW },
  ja: { translation: ja }, ru: { translation: ru }, vi: { translation: vi },
  es: { translation: es }, id: { translation: id }, uk: { translation: uk },
  tr: { translation: tr }, pt_BR: { translation: ptBR },
};

const normalize = value => String(value || '').replace('-', '_');
const saved = normalize(window.localStorage.getItem('ovpanel_language'));
const browser = normalize(window.navigator.language);
const initial = resources[saved] ? saved
  : resources[browser] ? browser
    : resources[browser.split('_')[0]] ? browser.split('_')[0] : 'en';

const applyDocumentLanguage = language => {
  const normalized = normalize(language);
  document.documentElement.lang = normalized.replace('_', '-');
  document.documentElement.dir = ['fa', 'ar'].includes(normalized) ? 'rtl' : 'ltr';
  document.documentElement.dataset.language = normalized;
};

i18n.use(initReactI18next).init({
  resources,
  lng: initial,
  fallbackLng: 'en',
  supportedLngs: Object.keys(resources),
  load: 'currentOnly',
  returnEmptyString: false,
  interpolation: { escapeValue: false },
});

applyDocumentLanguage(initial);
i18n.on('languageChanged', language => {
  const normalized = normalize(language);
  window.localStorage.setItem('ovpanel_language', normalized);
  applyDocumentLanguage(normalized);
});

export const t = (key, options) => i18n.t(key, options);
export default i18n;
