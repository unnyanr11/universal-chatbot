import { type StudioState } from "../useStudio";

export function SetupScreen({ studio }: { studio: StudioState }) {
  const ready = studio.docs.filter(
    (document) => document.status === "ready",
  ).length;
  const aiConfigured = studio.mode !== "extractive";
  const steps = [
    {
      title: "Make it yours",
      description:
        "Choose your assistant’s name, greeting, colour and suggested questions. Save a draft as you go.",
      destination: "Settings",
      action: "Personalise assistant",
      status: "Start here",
    },
    {
      title: "Add your business information",
      description:
        "Upload your FAQs, services or policies. Wait for sources to show Ready before testing answers.",
      destination: "Knowledge",
      action: "Add knowledge",
      status: ready ? `${ready} sources ready` : "Add your first source",
    },
    {
      title: "Try a conversation",
      description: aiConfigured
        ? "Ask a question your customers would ask. Check the answer and its source before sharing."
        : "You can test source-based answers now. To use AI-written answers, connect your AI service in Settings.",
      destination: "Chat",
      action: "Test assistant",
      status: aiConfigured
        ? "AI configured · test an answer"
        : "Source-based answers available",
    },
    {
      title: "Share on your website",
      description:
        "Review and publish your saved draft in Settings. Then enable guest chat and copy the installation code.",
      destination: "Integrate",
      action: "Set up website chat",
      status: "Publish when you’re ready",
    },
  ];
  return (
    <>
      <section className="panel setup-intro">
        <span className="eyebrow">YOUR FIRST ASSISTANT</span>
        <h2>From your business information to helpful answers.</h2>
        <p>
          Follow these four steps at your own pace. You can return here anytime.
          Nothing is shared publicly until you publish and enable guest chat.
        </p>
        <div className="button-row">
          <button onClick={() => studio.setTab("Settings")}>
            Connect or change AI service
          </button>
          <span className="muted">
            Already configured through your hosting settings? You can keep using
            that connection.
          </span>
        </div>
      </section>
      <ol className="setup-list" aria-label="Assistant setup steps">
        {steps.map((step, index) => (
          <li className="panel setup-step" key={step.title}>
            <span className="setup-number" aria-hidden="true">
              {index + 1}
            </span>
            <div>
              <span className="eyebrow">{step.status}</span>
              <h2>{step.title}</h2>
              <p>{step.description}</p>
              <button
                className={index === 0 ? "primary" : ""}
                onClick={() => studio.setTab(step.destination)}
              >
                {step.action} →
              </button>
            </div>
          </li>
        ))}
      </ol>
      <p className="fine">
        Appointments, team members and workflows are optional. Set them up later
        using the sidebar.
      </p>
    </>
  );
}
