import { Button, Text, View } from "react-native";

import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";


export function MockVoiceEntryPanel({
  sessionId,
  onSubmitted,
}: {
  sessionId: string | null;
  onSubmitted: () => void;
}) {
  const voiceDemo = useSendVoiceDemoMutation(sessionId);

  async function handleSubmit(kind: "query" | "stock_in") {
    const result = await voiceDemo.submitVoiceDemo(kind);
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  return (
    <View>
      <Text>Voice demos</Text>
      {voiceDemo.error ? <Text>{voiceDemo.error}</Text> : null}
      <Button
        title={voiceDemo.isSubmitting ? "Sending voice..." : "Voice Query Demo"}
        onPress={() => {
          void handleSubmit("query");
        }}
        disabled={voiceDemo.isSubmitting}
      />
      <Button
        title={voiceDemo.isSubmitting ? "Sending voice..." : "Voice Stock-In Demo"}
        onPress={() => {
          void handleSubmit("stock_in");
        }}
        disabled={voiceDemo.isSubmitting}
      />
    </View>
  );
}
