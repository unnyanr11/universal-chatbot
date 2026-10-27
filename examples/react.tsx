import { AssistantChat } from "../packages/react-sdk/AssistantChat";
// Integrate into your own React build. Obtain an ordinary application/guest session token
// through your same-origin backend. Never pass an upstream provider key to browser code.
export function BusinessChat({
  assistantId,
  sessionToken,
}: {
  assistantId: string;
  sessionToken: string;
}) {
  return (
    <AssistantChat
      assistantId={assistantId}
      token={sessionToken}
      mode="model"
    />
  );
}
