import { Children, cloneElement, useId, useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';

// Native modality makes the background inert and owns keyboard containment.
// Keep the existing inner layout and mutations separate from presentation.
export default function ModalOverlay({ children, onClose, className = 'modal-overlay' }) {
  const dialog = useRef(null);
  const latestClose = useRef(onClose);
  const titleId = useId();
  const { t } = useTranslation();
  const closeLabel = t('close', 'Close');
  useLayoutEffect(() => {
    for (const button of dialog.current.querySelectorAll('.close-modal-btn,.rename-modal-close')) {
      if (!button.getAttribute('aria-label')) button.setAttribute('aria-label', closeLabel);
    }
  }, [closeLabel]);
  useLayoutEffect(() => { latestClose.current = onClose; }, [onClose]);
  useLayoutEffect(() => {
    const node = dialog.current;
    const heading = node.querySelector('h2,h3');
    if (heading) {
      if (!heading.id) heading.id = titleId;
      node.setAttribute('aria-labelledby', heading.id);
    }
    node.showModal();
    return () => node.close();
  }, [titleId]);
  const content = cloneElement(Children.only(children), {
    role: undefined, 'aria-modal': undefined, 'aria-label': undefined, 'aria-labelledby': undefined,
  });
  const containFocus = event => {
    if (event.key !== 'Tab' || event.defaultPrevented) return;
    const controls = [...dialog.current.querySelectorAll('a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])')]
      .filter(element => !element.matches(':disabled') && element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden');
    const first = controls[0]; const last = controls.at(-1);
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  return createPortal(<dialog ref={dialog} className={`modal-native ${className}`}
    onKeyDown={containFocus}
    onCancel={event => { event.preventDefault(); latestClose.current?.(); }}>
    {content}
  </dialog>, document.body);
}
