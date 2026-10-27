import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function IntegrateScreen({ studio }: { studio: StudioState }) {
  const { assistant, setNotice, action } = studio;
  return (
    <section className="panel">
      <h2>Embed your assistant</h2>
      <p className="muted">
        Authenticated preview widget. Users sign in inside the isolated frame.
        Public guest sessions and host identity are pending.
      </p>
      <pre>{`<script async src="${location.origin}/widget-loader.js"\n  data-assistant="${assistant}"></script>`}</pre>
      <button
        onClick={() =>
          action(async () => {
            await navigator.clipboard.writeText(
              `<script async src="${location.origin}/widget-loader.js" data-assistant="${assistant}"></script>`,
            );
            setNotice("Embed code copied.");
          })
        }
      >
        Copy embed code
      </button>
      <h3>Integration boundaries</h3>
      <p>
        Serve the widget on a dedicated origin for isolation. Allow its origin
        in your host’s script-src and frame-src Content Security Policy. The
        loader does not collect page content or accept postMessage commands.
      </p>
      <p className="muted">
        Typed HTTP client: packages/js-sdk/index.ts. API schema: /openapi.json.
        Token streaming, guest access, mobile SDK and signed host identity
        remain pending.
      </p>
    </section>
  );
}
