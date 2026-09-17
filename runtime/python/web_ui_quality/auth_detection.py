"""Browser-side authentication-wall detection shared by runtime entry points.

An authentication wall is a visible credential gate for the page being
measured. A password input somewhere below the initial viewport is not, by
itself, evidence that the current page requires authentication.
"""

from __future__ import annotations


DOM_VISIBILITY_HELPER = r"""
  const hiddenBySemantics = (element) => {
    for (let node = element; node && node.nodeType === 1; node = node.parentElement) {
      if (node.hidden || String(node.getAttribute('aria-hidden') || '').toLowerCase() === 'true') return true;
    }
    return false;
  };
  const visibleElement = (element) => {
    if (!element || !element.isConnected || hiddenBySemantics(element)) return false;
    const style = getComputedStyle(element);
    if (typeof element.checkVisibility === 'function') {
      try {
        if (!element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return false;
      } catch (_error) {
        // Older Chromium versions may not support the options object.
      }
    }
    const rect = element.getBoundingClientRect();
    return style.display !== 'none'
      && style.visibility !== 'hidden'
      && Number(style.opacity || 1) > 0
      && rect.width > 0
      && rect.height > 0;
  };
  const fullyClipped = (element) => {
    const rect = element.getBoundingClientRect();
    for (let node = element; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      const clipPath = String(style.clipPath || 'none').replace(/\s+/g, '');
      if (/^inset\(100%(?:100%){0,3}\)$/i.test(clipPath)) return true;
      const clip = String(style.clip || 'auto').replace(/\s+/g, '');
      if (/^rect\(0(?:px)?,0(?:px)?,0(?:px)?,0(?:px)?\)$/i.test(clip)) return true;
      if (node !== element && /^(hidden|clip|scroll|auto)$/.test(style.overflow)) {
        const ancestorRect = node.getBoundingClientRect();
        if (rect.right <= ancestorRect.left || rect.left >= ancestorRect.right
          || rect.bottom <= ancestorRect.top || rect.top >= ancestorRect.bottom) return true;
      }
    }
    return false;
  };
  const inInitialViewport = (element) => {
    if (!visibleElement(element) || fullyClipped(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.bottom > 0
      && rect.top < window.innerHeight
      && rect.right > 0
      && rect.left < window.innerWidth;
  };
  const visibleInViewport = (element) => inInitialViewport(element);
"""


AUTH_WALL_HINT_SCRIPT = r"""
() => {
""" + DOM_VISIBILITY_HELPER + r"""
  const authWords = /登录|登陆|sign\s*in|log\s*in|login|验证码|verification code|authentication required|unauthorized/i;
  const accountSettingsWords = /current password|new password|confirm(?:ation)? password|change password|set password|account|profile|security|save|update/i;
  const credentialInput = (element) => element.matches(
    'input[type="password"], input[type="email"], input[autocomplete="username"], input[autocomplete="email"], input[name*="user" i], input[id*="user" i], input[name*="email" i], input[id*="email" i]'
  );
  const passwordInput = (element) => element.matches('input[type="password"]');
  const submitControl = (element) => element.matches(
    'button, input[type="submit"], input[type="button"], [role="button"]'
  );
  const controlName = (element) => (element.getAttribute('aria-label') || element.innerText || element.value || element.textContent || '').replace(/\s+/g, ' ').trim();
  const authAction = /登录|登陆|sign\s*in|log\s*in|login|authenticate|verify|continue\s+(?:with|to)|send\s+(?:code|otp)|sign\s+up/i;
  const visibleCredential = (root) => [...root.querySelectorAll('input')]
    .some((element) => visibleElement(element) && credentialInput(element));
  const visiblePassword = (root) => [...root.querySelectorAll('input')]
    .some((element) => visibleElement(element) && passwordInput(element));
  const visibleIdentity = (root) => [...root.querySelectorAll('input')]
    .some((element) => visibleElement(element) && element.matches('input[type="email"], input[autocomplete="username"], input[autocomplete="email"], input[name*="user" i], input[id*="user" i], input[name*="email" i], input[id*="email" i]'));
  const visibleControls = (root) => [...root.querySelectorAll('button, input, [role="button"]')]
    .filter((element) => visibleElement(element) && submitControl(element));
  const visibleSubmit = (root) => visibleControls(root).length > 0;
  const visibleAuthAction = (root) => visibleControls(root).some((element) => authAction.test(controlName(element)));
  const visibleText = (root) => [...root.querySelectorAll('*')]
    .filter(visibleElement)
    // Do not read an entire page-sized ancestor's innerText: its descendants
    // may be far below the viewport even when the ancestor intersects it.
    .filter((element) => element.children.length === 0 || element.matches('button, a, label, h1, h2, h3, h4, h5, h6'))
    .map((element) => element.innerText || element.textContent || '')
    .join(' ')
    .replace(/\s+/g, ' ')
    .slice(0, 4000);

  // Require a rendered credential control and a submit action in the same
  // form. Auth wording or login action semantics distinguish a login gate
  // from a public page's account/security settings form. The form may be
  // below the first viewport; viewport position is evidence, not authority.
  const formGate = [...document.querySelectorAll('form')].some((form) => {
    if (!visibleElement(form) || fullyClipped(form)) return false;
    const formText = visibleText(form);
    const identityPair = visiblePassword(form) && visibleIdentity(form) && !accountSettingsWords.test(formText);
    return visibleCredential(form)
      && visibleSubmit(form)
      && (authWords.test(formText) || visibleAuthAction(form) || identityPair);
  });

  // Some applications render a credential gate without a <form>. Limit the
  // fallback to a page/dialog surface with a real auth heading or auth error;
  // a public navigation "Sign in" button alone is not a wall.
  const inlineGate = [...document.querySelectorAll('[role="dialog"], [aria-modal="true"], main, [role="main"], section, article')]
    .some((surface) => {
      if (!visibleElement(surface) || fullyClipped(surface)) return false;
      const surfaceText = visibleText(surface);
      const headingText = [...surface.querySelectorAll('h1, h2, h3, [role="heading"]')]
        .filter(visibleElement)
        .map((element) => controlName(element))
        .join(' ');
      const hasAuthHeading = authWords.test(headingText) || /sign\s+in\s+to\s+continue|login\s+required|authentication required|unauthorized/i.test(surfaceText);
      const hasCredential = visibleCredential(surface);
      const hasPassword = visiblePassword(surface);
      const hasAuthAction = visibleAuthAction(surface);
      return hasAuthAction && authWords.test(surfaceText)
        && (hasAuthHeading || hasCredential || hasPassword);
    });

  return Boolean(formGate || inlineGate);
}
"""


__all__ = ["AUTH_WALL_HINT_SCRIPT"]
