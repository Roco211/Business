import { ScrollView, Text, View } from "react-native";

import { useSessionStream } from "../../../shared/session/useSessionStream";


function describeEvent(event: {
  event_type: string;
  occurred_at: string;
  data: Record<string, unknown>;
}) {
  const previewText = typeof event.data.preview_text === "string" ? event.data.preview_text : null;
  if (previewText) {
    return previewText;
  }
  const summary = typeof event.data.summary === "string" ? event.data.summary : null;
  if (summary) {
    return summary;
  }
  const status = typeof event.data.status === "string" ? event.data.status : null;
  if (status) {
    return status;
  }
  return event.occurred_at;
}


export default function ChatScreen() {
  const sessionStream = useSessionStream();
  const title = sessionStream.sessionTitle ?? sessionStream.sessionId ?? "工作群";

  return (
    <ScrollView>
      <Text>{title}</Text>
      <Text>{sessionStream.connectionState}</Text>

      {sessionStream.bootstrapError ? (
        <View>
          <Text>Session unavailable</Text>
          <Text>{sessionStream.bootstrapError}</Text>
        </View>
      ) : null}

      <Text>Recent session events</Text>
      {sessionStream.recentEvents.length === 0 ? <Text>No recent session events yet.</Text> : null}
      {sessionStream.recentEvents.map((event) => (
        <View key={event.event_id}>
          <Text>{event.event_type}</Text>
          <Text>{describeEvent(event)}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
