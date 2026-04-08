import { useEffect, useRef, useState } from "react";
import type { RouteProp } from "@react-navigation/native";
import { ScrollView, StyleSheet, View } from "react-native";

import type { RootTabParamList } from "../../../app/navigation/rootTabConfig";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";
import { useSessionStream } from "../../../shared/session/useSessionStream";
import {
  AppScreen,
  AppTextField,
  DebugDisclosure,
  EmptyState,
  InlineNotice,
  PrimaryButton,
  SectionHeader,
  SurfaceCard,
  space,
} from "../../../shared/ui";
import { GuidedEntryDock } from "../components/GuidedEntryDock";
import { MessageResultCard } from "../components/MessageResultCard";
import { MockMediaEntryPanel } from "../components/MockMediaEntryPanel";
import { PendingReceiptConfirmationCard } from "../components/PendingReceiptConfirmationCard";
import { PendingStockInConfirmationCard } from "../components/PendingStockInConfirmationCard";
import { PendingStockOutConfirmationCard } from "../components/PendingStockOutConfirmationCard";
import { WorkbenchHeader } from "../components/WorkbenchHeader";
import { useChatPendingConfirmationsQuery } from "../hooks/useChatPendingConfirmationsQuery";
import { useSendMessageMutation } from "../hooks/useSendMessageMutation";
import { useSessionMessagesQuery } from "../hooks/useSessionMessagesQuery";
import { presentRuntimeMessageText } from "../utils/presentRuntimeMessageText";
import { WORKBENCH_INTENT_COPY, type WorkbenchIntent } from "../workbenchIntent";

type ChatScreenProps = {
  route?: RouteProp<RootTabParamList, "workbench">;
};

const COPY = {
  fallbackSessionTitle: "工作台会话",
  loadingTitle: "正在同步工作台",
  loadingDescription: "请稍候，我们正在整理会话消息与待确认事项。",
  workbenchTitle: "聊天工作台",
  sessionUnavailable: "当前会话暂时不可用",
  messagesUnavailable: "消息列表暂时不可用",
  confirmationsUnavailable: "待确认事项暂时不可用",
  taskFirstTitle: "从这里开始",
  taskFirstSubtitle: "先完成任务入口，再发送文字补充。",
  pendingTitle: "待确认",
  pendingSubtitle: "优先完成需要人工复核的项目。",
  latestResultsTitle: "最新结果",
  latestResultsSubtitle: "完成当前任务后再向下查看。",
  emptyTitle: "工作台里还没有新消息",
  emptyDescription: "可以先用引导入口，也可以直接发送文字请求。",
  composeTitle: "发送输入",
  composeSubtitle: "可直接输入详细请求。",
  messageLabel: "消息",
  messagePlaceholder: "描述你的请求",
  sendFailed: "发送未完成",
  sendAction: "发送消息",
  sendLoading: "正在发送...",
  actorOwner: "店主",
  actorSystem: "系统",
  actorFallback: "参与方",
  messageFallback: "此消息暂无可显示内容",
  debugTools: "调试工具",
} as const;

function getActorLabel(actorType: string) {
  if (actorType === "owner") {
    return COPY.actorOwner;
  }
  if (actorType === "system") {
    return COPY.actorSystem;
  }
  return COPY.actorFallback;
}

function getMessageText(actorType: string, actorId: string, text: string | null) {
  if (text && text.trim().length > 0) {
    const presentedText = presentRuntimeMessageText(text, {
      isRuntimeSystemMessage: actorType === "system" && actorId === "runtime",
    });
    if (presentedText.trim().length > 0) {
      return presentedText;
    }
  }
  return COPY.messageFallback;
}

export default function ChatScreen({ route }: ChatScreenProps = {}) {
  const sessionStream = useSessionStream();
  const [draftText, setDraftText] = useState("");
  const scrollViewRef = useRef<ScrollView | null>(null);
  const [pendingOffset, setPendingOffset] = useState(0);

  const sessionTitle =
    sessionStream.sessionTitle ?? sessionStream.sessionId ?? COPY.fallbackSessionTitle;
  const initialIntent: WorkbenchIntent | null = route?.params?.initialIntent ?? null;
  const intentCopy = initialIntent ? WORKBENCH_INTENT_COPY[initialIntent] : null;

  const messages = useSessionMessagesQuery(sessionStream.sessionId);
  const confirmations = useChatPendingConfirmationsQuery(sessionStream.sessionId);
  const sendMessage = useSendMessageMutation(sessionStream.sessionId);

  function refreshChat() {
    messages.refresh();
    confirmations.refresh();
  }

  useEffect(() => {
    const eventType = sessionStream.lastEvent?.event_type;
    if (
      eventType !== "message.created"
      && eventType !== "task.updated"
      && eventType !== "confirmation.created"
      && eventType !== "confirmation.resolved"
      && eventType !== "inventory.updated"
    ) {
      return;
    }
    refreshChat();
  }, [sessionStream.lastEvent?.event_id]);

  useEffect(() => {
    if (sessionStream.dataResetVersion === 0) {
      return;
    }
    refreshChat();
  }, [sessionStream.dataResetVersion]);

  useEffect(() => {
    if (initialIntent === "pending-confirmations" && pendingOffset > 0) {
      scrollViewRef.current?.scrollTo({ y: Math.max(pendingOffset - space.s12, 0), animated: false });
    }
  }, [initialIntent, pendingOffset]);

  async function handleSend() {
    const result = await sendMessage.submitMessage(draftText);
    if (result === null) {
      return;
    }
    setDraftText("");
    refreshChat();
  }

  if (messages.isLoading && messages.data.length === 0) {
    return (
      <AppScreen safeArea={false}>
        <EmptyState title={COPY.loadingTitle} description={COPY.loadingDescription} />
      </AppScreen>
    );
  }

  return (
    <AppScreen safeArea={false}>
      <ScrollView ref={scrollViewRef} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <WorkbenchHeader
          title={COPY.workbenchTitle}
          sessionTitle={sessionTitle}
          connectionState={sessionStream.connectionState}
          bootstrapError={sessionStream.bootstrapError}
          onAction={refreshChat}
        />

        {sessionStream.bootstrapError ? (
          <InlineNotice
            tone="error"
            title={COPY.sessionUnavailable}
            message={getFriendlyStatusMessage(sessionStream.bootstrapError, "请稍后再试。")}
          />
        ) : null}
        {messages.error ? (
          <InlineNotice
            tone="error"
            title={COPY.messagesUnavailable}
            message={getFriendlyStatusMessage(messages.error, "请稍后再试。")}
          />
        ) : null}
        {confirmations.error ? (
          <InlineNotice
            tone="error"
            title={COPY.confirmationsUnavailable}
            message={getFriendlyStatusMessage(confirmations.error, "请稍后再试。")}
          />
        ) : null}

        {intentCopy ? (
          <InlineNotice tone="neutral" title={intentCopy.workbenchTitle} message={intentCopy.workbenchHint} />
        ) : null}

        <SurfaceCard emphasis="elevated">
          <SectionHeader title={COPY.taskFirstTitle} subtitle={COPY.taskFirstSubtitle} />
          <GuidedEntryDock
            sessionId={sessionStream.sessionId}
            onSubmitted={refreshChat}
            highlightedIntent={initialIntent}
          />
        </SurfaceCard>

        <View onLayout={(event) => setPendingOffset(event.nativeEvent.layout.y)} style={styles.timelineGroup}>
          <SectionHeader title={COPY.pendingTitle} subtitle={COPY.pendingSubtitle} />
          {confirmations.data.map((confirmation) =>
            confirmation.confirmation_type === "receipt-stock-in-batch" ? (
              <PendingReceiptConfirmationCard
                key={confirmation.confirmation_id}
                confirmation={confirmation}
                onResolved={refreshChat}
              />
            ) : confirmation.confirmation_type === "stock-out" ? (
              <PendingStockOutConfirmationCard
                key={confirmation.confirmation_id}
                confirmation={confirmation}
                onResolved={refreshChat}
              />
            ) : (
              <PendingStockInConfirmationCard
                key={confirmation.confirmation_id}
                confirmation={confirmation}
                onResolved={refreshChat}
              />
            ),
          )}
        </View>

        <SectionHeader title={COPY.latestResultsTitle} subtitle={COPY.latestResultsSubtitle} />
        {messages.data.length === 0 ? (
          <EmptyState title={COPY.emptyTitle} description={COPY.emptyDescription} />
        ) : null}

        {messages.data.map((message) => (
          <View key={message.message_id} style={styles.timelineGroup}>
            <MessageResultCard
              messageId={message.message_id}
              actorLabel={getActorLabel(message.actor_type)}
              actorType={message.actor_type}
              messageType={message.message_type}
              text={getMessageText(message.actor_type, message.actor_id, message.text)}
              createdAt={message.created_at}
            />
          </View>
        ))}

        <SurfaceCard emphasis="elevated">
          <View style={styles.composer}>
            <SectionHeader title={COPY.composeTitle} subtitle={COPY.composeSubtitle} />
            <AppTextField
              label={COPY.messageLabel}
              placeholder={COPY.messagePlaceholder}
              value={draftText}
              onChangeText={setDraftText}
            />
            {sendMessage.error ? (
              <InlineNotice
                tone="error"
                title={COPY.sendFailed}
                message={getFriendlyStatusMessage(sendMessage.error, "请稍后再试。")}
              />
            ) : null}
            <PrimaryButton
              label={COPY.sendAction}
              loading={sendMessage.isSubmitting}
              loadingLabel={COPY.sendLoading}
              onPress={() => {
                void handleSend();
              }}
              disabled={sendMessage.isSubmitting}
            />
            <DebugDisclosure title={COPY.debugTools}>
              <MockMediaEntryPanel sessionId={sessionStream.sessionId} onSubmitted={refreshChat} />
            </DebugDisclosure>
          </View>
        </SurfaceCard>
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: space.s12,
    paddingBottom: space.s24,
  },
  timelineGroup: {
    gap: space.s8,
  },
  composer: {
    gap: space.s12,
  },
});
