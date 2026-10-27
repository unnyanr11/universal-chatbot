import { type StudioState } from "../useStudio";
import { Onboarding } from "../features/Onboarding";
import { Installation } from "../features/Installation";
import {
  Enquiries,
  IntegrationDiagnostics,
  WebhookSettings,
} from "../features/IntegrationDiagnostics";
export function IntegrateScreen({ studio }: { studio: StudioState }) {
  if (!studio.assistant) return <p>Create an assistant first.</p>;
  return (
    <>
      <Onboarding
        key={studio.assistant + "-onboard"}
        assistant={studio.assistant}
        onChanged={() => {
          void studio.refreshBranding();
          void studio.refreshDocs();
        }}
      />
      <Installation
        key={studio.assistant + "-install"}
        assistant={studio.assistant}
      />
      <IntegrationDiagnostics
        key={studio.assistant + "-diagnostics"}
        assistant={studio.assistant}
      />
      <Enquiries
        key={studio.assistant + "-enquiries"}
        assistant={studio.assistant}
      />
      <WebhookSettings key={studio.project} project={studio.project} />
    </>
  );
}
