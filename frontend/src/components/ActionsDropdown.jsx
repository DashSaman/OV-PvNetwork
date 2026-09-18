import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FiMoreVertical } from 'react-icons/fi';

const ActionsDropdown = ({ actions = [] }) => {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const locate = () => {
    if (!triggerRef.current) return;

    const r = triggerRef.current.getBoundingClientRect();
    const width = Math.min(210, window.innerWidth - 16);
    const height = Math.min(
      Math.max(actions.length * 44 + 12, 60),
      Math.max(120, window.innerHeight - 16)
    );

    const left = Math.max(
      8,
      Math.min(
        r.right - width,
        window.innerWidth - width - 8
      )
    );

    let top = r.bottom + 6;

    if (top + height > window.innerHeight - 8) {
      top = Math.max(
        8,
        r.top - height - 6
      );
    }

    setPos({ top, left });
  };

  useEffect(() => {
    if (!open) return;

    locate();

    const outside = (e) => {
      if (
        triggerRef.current?.contains(e.target) ||
        menuRef.current?.contains(e.target)
      ) {
        return;
      }

      setOpen(false);
    };

    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    const reposition = () => locate();

    document.addEventListener('mousedown', outside, true);
    document.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);

    const firstItem = menuRef.current?.querySelector('[role="menuitem"]');
    firstItem?.focus();

    return () => {
      document.removeEventListener('mousedown', outside, true);
      document.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  }, [open, actions.length]);

  return (
    <>
      <div className="actions-dropdown-container">
        <button
          ref={triggerRef}
          type="button"
          className="actions-dropdown-trigger"
          aria-label="Open actions menu"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();

            if (!open) locate();
            setOpen(v => !v);
          }}
        >
          <FiMoreVertical size={20} aria-hidden="true" focusable="false" />
        </button>
      </div>

      {open &&
        createPortal(
          <div
            ref={menuRef}
            className="actions-dropdown-menu"
            role="menu"
            aria-label="Available actions"
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              right: 'auto',
              minWidth: Math.min(210, Math.max(0, window.innerWidth - 16)),
              zIndex: 999999,
            }}
          >
            {actions.map((action, index) => (
              <button
                key={index}
                type="button"
                role="menuitem"
                className={`actions-dropdown-item ${action.className || ''}`}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setOpen(false);
                  action.onClick();
                }}
              >
                {action.label}
              </button>
            ))}
          </div>,
          document.body
        )}
    </>
  );
};

export default ActionsDropdown;
