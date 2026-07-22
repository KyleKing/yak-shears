# 0008: Mobile Text-Entry Affordances on iOS

## Status

Accepted (2026-07-22). The in-page accessory toolbar is landing in the same round as this record.

## Context

Notes get edited on an iPhone 14, in mobile Safari and from the homescreen web app. The editor is CodeJar over a `contenteditable`, and its structural commands are bound to keys that iOS does not have:

- list indent and outdent are `Tab` and `Shift+Tab`
- the checklist toggle is `Ctrl+L`

The iOS software keyboard has no `Tab` key and no `Ctrl`, so on a phone those commands are unreachable. Screen budget makes it worse: Safari's URL bar sits above the page and the keyboard sits below it, leaving a narrow window of actual editor (screenshot `5-Keyboard.PNG`). Apple Notes on the same device puts a bar of formatting controls directly above the keyboard, which is the experience being asked for.

The question to answer: can a web app supply a keyboard like that, could it be published separately as a general-purpose iOS custom keyboard, or does this need a full native app?

## What Apple Notes actually uses

Notes draws its bar through `inputAccessoryView`, a UIKit property on `UIResponder`. A native app hands the system a view, the system pins it above the keyboard, and the app keeps it in sync with the current selection. Safari uses the same mechanism for its own bar, which is the previous/next arrows and the checkmark visible in `7-Overlay.PNG`.

A web page cannot supply one. `inputAccessoryView` is a UIKit API on the native responder chain, and WebKit exposes no web-platform hook for a page to replace or extend Safari's own accessory view. The page is content inside the browser's responder, so the browser owns that bar.

## What the web platform does give on iOS

- [`visualViewport`](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport) reports the height, offset, and scale of the part of the page actually visible, and fires `resize` and `scroll` when the keyboard opens, closes, or the page scrolls under it. Comparing `window.innerHeight` against `visualViewport.height + visualViewport.offsetTop` gives a usable keyboard height. Baseline widely available since August 2021, and this is the mechanism iOS web apps use to position anything above the keyboard
- The [VirtualKeyboard API](https://developer.mozilla.org/en-US/docs/Web/API/VirtualKeyboard_API) (`navigator.virtualKeyboard.overlaysContent`, the `geometrychange` event, and the `env(keyboard-inset-*)` CSS variables) is the purpose-built version of the same idea, and it is [Chromium 94+ only](https://developer.chrome.com/docs/web-platform/virtual-keyboard). Safari does not support it, so it cannot be the primary path here
- [`inputmode`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/inputmode) picks which system keyboard appears (text, numeric, url, and so on) and [`enterkeyhint`](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/enterkeyhint) relabels the return key. Both change the keyboard the system already has. Neither adds a key or a bar

The ceiling for a web page on iOS is therefore a bar drawn inside the page and positioned above the keyboard by hand.

## Options considered

### Option A: in-page accessory toolbar (chosen)

A `position: fixed` bar in the edit template, offset from the bottom by the measured keyboard height, holding outdent, indent, bullet, checklist, bold, italic, and a dismiss button. Each button calls the same editor command the desktop key binding calls. Buttons call `preventDefault` on `pointerdown` so the `contenteditable` never loses focus and the keyboard is not dismissed by the tap.

Costs nothing beyond the app itself, ships on the next deploy, works in Safari and in the homescreen web app, and stays in sync with the editor because it is the editor.

### Option B: publish an iOS custom keyboard extension

A keyboard extension is a real extension type, and it is the wrong shape for this problem on nearly every axis.

- It cannot be published on its own. Per Apple's [App Extension Programming Guide](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/CustomKeyboard.html), the extension ships inside a containing app, and "before you submit a containing app to the App Store, it must perform some useful function." So there is an App Store app to build, ship, and maintain either way
- It replaces the whole keyboard rather than adding a bar. Every letter, number, shift state, emoji picker, and language layout becomes something to reimplement, and the guide requires a next-keyboard affordance so the user can switch back
- Users must turn it on by hand in Settings > General > Keyboard > Keyboards, then pick it with the globe key each time the system keyboard comes up somewhere else
- Anything nontrivial needs `RequestsOpenAccess` (the "Allow Full Access" toggle). Without it the extension gets no network and no shared container with its app. With it, the extension can send keystrokes anywhere, which is the reason users are cautious about third-party keyboards. Apple's [App Review Guidelines 4.4.1](https://developer.apple.com/app-store/review/guidelines/) further requires keyboard extensions to "remain functional without full network access and without requiring full access", so full access cannot be a hard dependency
- It cannot be scoped to one website. An extension has no way to know that the host app is Safari showing yak-shears rather than a mail composer, so an indent button either appears everywhere or nowhere
- The documented job of a keyboard extension is to "provide text, in the form of an unattributed `NSString` object, at the text insertion point". That is text insertion, so a page listening for a `Tab` keydown would not see one, and the indent command would still not fire (inferred from the documented API surface, not measured)
- Guideline 4.4.1 also forbids repurposing keyboard buttons for other behaviors, which is close to what a hidden indent gesture would be

### Option C: thin native shell (WKWebView plus a native accessory view)

A small native app hosting the site in a `WKWebView`, with a native `inputAccessoryView` attached to the web view and a message bridge calling into the editor's JS commands. This is the one thing a wrapper genuinely buys here that the web cannot do: a real system accessory bar, sized and animated by the system, that no viewport arithmetic can fully imitate. It also removes the URL bar and the in-app browser overlay (ADR 0009) as side effects.

Costs an Xcode project, a developer account, and App Store or TestFlight distribution for a single user, and every editor change now has two surfaces to keep in step.

### Option D: full native iOS app

A native editor over the vault, no web view. Best possible text entry (real accessory view, real gestures, real offline). Largest cost by a wide margin, and it duplicates the whole product.

## Decision

Option A now. The in-page toolbar reaches the same commands as the desktop key bindings, ships with the app, and needs no App Store presence. A custom keyboard extension does not solve this problem, because it cannot be scoped to one site, cannot be shipped without a containing app, and would replace the system keyboard rather than augment it.

## Consequences

- The toolbar appears only while the editor on this page has focus. It cannot show up over any other app's text field, which is exactly what Option B would have bought and Option A does not
- Positioning depends on `visualViewport`. The bar has to re-measure on `resize` and `scroll`, and iOS fires those during keyboard animation, so the bar can lag the keyboard by a frame or two
- The bar competes for the same vertical space as the keyboard and the URL bar. It has to stay one row, and it deliberately includes a dismiss button so the editor can be reclaimed
- Buttons must `preventDefault` on `pointerdown`. Without it the tap blurs the `contenteditable`, the keyboard closes, and the selection the command was meant to act on is gone
- The desktop key bindings stay as they are. The toolbar is a second entry point to the same commands, not a replacement

## Revisit when

- The bar's position proves unfixable against iOS keyboard animation or the homescreen web app, and a native accessory view becomes the only way to get it right
- Offline editing becomes a real requirement (ADR 0009 keeps this open), because that is the other half of the case for Option C or D and the two should be decided together
- The Syncthing-vault-direct sibling app sketched in ROADMAP.md's "Workout planner (deferred)" gets built, since that app would already own the native surface a shell would need
- Safari ships the VirtualKeyboard API, which would replace the viewport arithmetic with `env(keyboard-inset-height)` and make Option A meaningfully sturdier
