# Client integrations

All clients use the same authenticated `/v1` HTTP API and server-owned conversations. Public assistant IDs are locators, not secrets or authentication. Never embed owner/developer credentials in a client bundle. Tokens are one-hour opaque sessions and can be revoked server-side.

## Website widget

Use Integrate in Studio to copy the lazy iframe loader. Serve it on a dedicated origin in a host application and allow that origin in CSP script-src/frame-src. The loader has no general postMessage bridge and collects no page contents. It is an authenticated widget; guest sessions and signed host identity are not yet provided; configured embedding hosts are enforced through frame-ancestors. Frame policies are defence in depth, not authentication.

## React

`packages/react-sdk/AssistantChat.tsx` is a reusable typed React source component. Import it in a TypeScript bundler app and supply `assistantId`, `apiBase` and a short-lived token obtained through an authenticated application flow. The component supports cancellation, error states, safe text rendering and source callbacks. It does not accept generated HTML. `packages/js-sdk` exposes the HTTP client and incremental SSE reader.

The source component is type-checked separately by `tsc -p packages/react-sdk/tsconfig.json`. It is not published to npm. Cross-origin direct API access is disabled by default; use a reviewed reverse proxy or same-origin application integration until explicit restricted CORS and signed host identity are implemented.

## React Native / Expo source example

`apps/demo-mobile/App.tsx` demonstrates the same API with keyboard-safe layout, token storage in Expo SecureStore, abort handling and source-aware replies. It is source for an Expo app, not a verified mobile release. Create an Expo TypeScript application with the current official Expo tooling, install `expo-secure-store` using `npx expo install expo-secure-store`, and copy the component plus the JS client with the relative import adjusted for that app. Pin the generated project dependencies and lock file before distributing it.

`EXPO_PUBLIC_API_URL` is a public application API origin, never a model-server URL or a privileged secret. Android emulators can use `http://10.0.2.2:8000`; physical devices need a reachable development host. Use TLS outside loopback/local synthetic testing and configure trusted network access deliberately. The example requires device/emulator acceptance; it has not been tested on a phone here. Reauthenticate when sessions expire; the example retains the current conversation while mounted, and history endpoints allow explicit resume.

Flutter and voice remain optional, unimplemented adapters. Nothing silently falls back to screen scraping or an unconfigured external connector.

Configured generation uses `mode: "model"`; `extractive` remains a generation-free option. The React component supports an optional `mode="model"` prop. Configure provider credentials on the server or in assistant Settings; applications only receive ordinary short-lived session tokens. See PROVIDERS.md.
