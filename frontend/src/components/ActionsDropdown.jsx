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
    const width = 210;
    const height = Math.min(
      Math.max(actions.length * 44 + 12, 60),
      340
    );

    let left = Math.max(
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

    const reposition = () => locate();

    document.addEventListener(
      'mousedown',
      outside,
      true
    );

    window.addEventListener(
      'resize',
      reposition
    );

    window.addEventListener(
      'scroll',
      reposition,
      true
    );

    return () => {
      document.removeEventListener(
        'mousedown',
        outside,
        true
      );

      window.removeEventListener(
        'resize',
        reposition
      );

      window.removeEventListener(
        'scroll',
        reposition,
        true
      );
    };
  }, [open, actions.length]);

  return (
    <>
      <div className="actions-dropdown-container">
        <button
          ref={triggerRef}
          type="button"
          className="actions-dropdown-trigger"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();

            if (!open) locate();

            setOpen(v => !v);
          }}
        >
          <FiMoreVertical size={20} />
        </button>
      </div>

      {open &&
        createPortal(
          <div
            ref={menuRef}
            className="actions-dropdown-menu"
            style={{
              position: 'fixed',
              top: pos.top,
              left: pos.left,
              right: 'auto',
              minWidth: 210,
              zIndex: 999999,
            }}
          >
            {actions.map((action, index) => (
              <button
                key={index}
                type="button"
                className={`actions-dropdown-item ${
                  action.className || ''
                }`}
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
