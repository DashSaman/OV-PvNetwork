// Measure author outlines against the actual adjacent opaque/composited surface.
// Gradients/opacity require separate review; never silently count them as passes.
async function measureContrast(page, selector) {
  return page.evaluate(selector => {
    const element = selector ? document.querySelector(selector) : document.activeElement;
    const style = getComputedStyle(element);
    const parse = value => (value.match(/[\d.]+/g) || []).map(Number);
    const luminance = values => values.slice(0, 3).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const layers = [];
    if (Number(style.opacity) < 1) return { manual: true, reason: 'Control opacity' };
    for (let parent = selector ? element : element.parentElement; parent; parent = parent.parentElement) {
      const surface = getComputedStyle(parent);
      if (surface.backgroundImage !== 'none' || Number(surface.opacity) < 1) return { manual: true, reason: 'Gradient/image/ancestor opacity' };
      const layer = parse(surface.backgroundColor);
      const alpha = layer[3] ?? 1;
      if (!alpha) continue;
      layers.push([...layer.slice(0, 3), alpha]);
      if (alpha === 1) {
        let background = layers.pop().slice(0, 3);
        for (const [red, green, blue, opacity] of layers.reverse()) background = [red, green, blue].map((v, i) => v * opacity + background[i] * (1 - opacity));
        const ink = parse(selector ? style.color : style.outlineColor), opacity = ink[3] ?? 1;
        const foreground = luminance(ink.slice(0, 3).map((v, i) => v * opacity + background[i] * (1 - opacity))), behind = luminance(background);
        return { manual: false, ratio: (Math.max(foreground, behind) + .05) / (Math.min(foreground, behind) + .05), foreground: selector ? style.color : style.outlineColor, background };
      }
    }
    return { manual: true, reason: 'No resolved opaque adjacent surface' };
  }, selector);
}
export const focusContrast = page => measureContrast(page, null);
export const textContrast = (page, selector) => measureContrast(page, selector);
