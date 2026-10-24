<script setup lang="ts">
import { BookOpen, Bot, User, Wrench } from "lucide-vue-next";
import { computed, ref } from "vue";

import type { ChatMessage, ToolCallAudit } from "@agent-py/api-contracts";
import type { ChatReference, LiveToolCall } from "../stores/chat";
import AppLoadingState from "./AppLoadingState.vue";
import AsyncStatusBadge from "./AsyncStatusBadge.vue";
import ChatCitationDetail from "./ChatCitationDetail.vue";
import MarkdownContent from "./MarkdownContent.vue";
import RetrievalStageTrace from "./RetrievalStageTrace.vue";
import UserFeedbackControl from "./UserFeedbackControl.vue";

const emit = defineEmits<{ "open-document": [reference: ChatReference] }>();
const props = defineProps<{
  readonly isLoading: boolean;
  readonly liveToolCalls: readonly LiveToolCall[];
  readonly messages: readonly ChatMessage[];
  readonly references: readonly ChatReference[];
  readonly toolAudits: readonly ToolCallAudit[];
}>();

const selectedCitation = ref<ChatReference | null>(null);
const selectedCitationMessageId = ref<string | null>(null);
const latestAssistantMessageId = computed(() =>
  [...props.messages].reverse().find((message) => message.role === "assistant")?.id ?? null
);

function selectCitation(reference: ChatReference, messageId: string | null): void {
  selectedCitation.value = reference;
  selectedCitationMessageId.value = messageId;
}

function canCollectFeedback(message: ChatMessage): boolean {
  return message.role === "assistant" && !message.id.startsWith("message_draft_");
}

function isStreamingDraft(message: ChatMessage): boolean {
  return message.id.startsWith("message_draft_");
}

function sourceLabel(reference: ChatReference): string {
  if (reference.knowledgeType === "sop") return "SOP";
  if (reference.knowledgeType === "diagnostic-case") return "故障案例";
  return reference.knowledgeType === "document" || reference.sourceType === "document"
    ? "知识库"
    : reference.sourceType;
}

function messageAudits(message: ChatMessage): readonly ToolCallAudit[] {
  const ids = new Set(message.metadata.toolCallIds ?? []);
  return props.toolAudits.filter((audit) => ids.has(audit.id));
}
</script>

<template>
  <section class="chat-transcript" aria-label="当前对话">
    <AppLoadingState v-if="isLoading" label="正在加载对话" />
    <ol v-else-if="messages.length > 0" class="chat-transcript__messages">
      <li v-for="message in messages" :key="message.id" :class="`chat-transcript__message--${message.role}`">
        <article
          class="chat-transcript__message"
          :class="`chat-transcript__row--${message.role}`"
        >
          <span class="chat-transcript__avatar" :class="`chat-transcript__avatar--${message.role}`" aria-hidden="true">
            <Bot v-if="message.role === 'assistant'" :size="16" />
            <User v-else :size="15" />
          </span>
          <div class="chat-transcript__content">
            <span class="chat-transcript__role">
              <Bot v-if="message.role === 'assistant'" :size="13" aria-hidden="true" />{{ message.role === "assistant" ? "助手" : "你" }}
            </span>
            <div class="chat-transcript__bubble" :class="`chat-transcript__bubble--${message.role}`">
              <MarkdownContent v-if="message.role === 'assistant'" :content="message.content" />
              <p v-else>{{ message.content }}</p>
              <div
                v-if="message.role === 'assistant' && isStreamingDraft(message)"
                class="chat-transcript__typing"
                role="status"
                aria-label="正在生成回答"
              >
                <span></span><span></span><span></span>
              </div>
              <ul
                v-if="message.metadata.citations?.length"
                class="chat-transcript__message-sources"
                aria-label="回答引用来源"
              >
                <li v-for="reference in message.metadata.citations" :key="reference.id">
                  <button type="button" :aria-label="`查看 ${reference.title} 的来源详情`" @click="selectCitation(reference, message.id)"><BookOpen :size="13" aria-hidden="true" />{{ reference.title }}</button>
                  <RetrievalStageTrace :reference="reference" compact />
                  <UserFeedbackControl v-if="canCollectFeedback(message)" target-type="citation" :target-id="message.id" :subject-id="reference.id" compact />
                </li>
              </ul>
              <div v-if="canCollectFeedback(message)" class="chat-transcript__message-footer">
                <UserFeedbackControl target-type="chat_message" :target-id="message.id" compact />
              </div>
              <details v-if="message.role === 'assistant' && messageAudits(message).length" class="chat-transcript__details"><summary><Wrench :size="14" aria-hidden="true" />工具调用（{{ messageAudits(message).length }}）</summary><ul><li v-for="audit in messageAudits(message)" :key="audit.id"><span>{{ audit.toolName }}</span><AsyncStatusBadge :status="audit.status" compact /><small v-if="audit.resultSummary || audit.errorMessage">{{ audit.resultSummary ?? audit.errorMessage }}</small></li></ul></details>
              <details v-if="message.role === 'assistant' && message.metadata.reasoning?.length" class="chat-transcript__details"><summary>深度思考</summary><p>{{ message.metadata.reasoning.join('') }}</p></details>
            </div>
          </div>
        </article>
      </li>
    </ol>
    <aside v-if="liveToolCalls.length > 0" class="chat-transcript__context" aria-label="正在进行的工具调用">
      <h2><Wrench :size="15" aria-hidden="true" />工具调用</h2>
      <ul>
        <li v-for="tool in liveToolCalls" :key="tool.id"><span>{{ tool.name }}</span><AsyncStatusBadge :status="tool.status" compact /></li>
      </ul>
    </aside>
    <aside v-if="references.length > 0" class="chat-transcript__context" aria-label="本次回答引用的来源">
      <h2><BookOpen :size="15" aria-hidden="true" />本次回答引用</h2>
      <ul><li v-for="reference in references" :key="reference.id"><div class="chat-transcript__reference-heading"><span>{{ sourceLabel(reference) }}</span><button type="button" :aria-label="`查看 ${reference.title} 的来源详情`" @click="selectCitation(reference, latestAssistantMessageId)">{{ reference.title }}</button></div><RetrievalStageTrace :reference="reference" compact /><UserFeedbackControl v-if="latestAssistantMessageId" target-type="citation" :target-id="latestAssistantMessageId" :subject-id="reference.id" compact /></li></ul>
    </aside>
    <ChatCitationDetail v-if="selectedCitation && selectedCitationMessageId" :message-id="selectedCitationMessageId" :reference="selectedCitation" @close="selectedCitation = null; selectedCitationMessageId = null" @open-document="emit('open-document', $event)" />
  </section>
</template>

<style scoped>
.chat-transcript { display: grid; gap: 1.35rem; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 1.75rem clamp(1rem, 4vw, 4.5rem); scrollbar-color: var(--line-strong) transparent; }
.chat-transcript__messages { display: grid; gap: 1.3rem; list-style: none; margin: 0; padding: 0; }
.chat-transcript__message--user { display: flex; justify-content: flex-end; }
.chat-transcript__message { display: flex; gap: 0.7rem; max-width: min(50rem, 100%); min-width: 0; }
.chat-transcript__row--user { flex-direction: row-reverse; }
.chat-transcript__avatar { align-items: center; border-radius: 50%; display: inline-flex; flex-shrink: 0; height: 2rem; justify-content: center; margin-top: 0.05rem; width: 2rem; }
.chat-transcript__avatar--assistant { background: linear-gradient(140deg, #16a97f, var(--accent-strong)); box-shadow: inset 0 0 0 1px rgb(255 255 255 / 22%); color: #ffffff; }
.chat-transcript__avatar--user { background: var(--surface-inset); border: 1px solid var(--line-strong); color: var(--text-secondary); }
.chat-transcript__content { display: grid; gap: 0.4rem; max-width: 100%; min-width: 0; }
.chat-transcript__role { align-items: center; color: var(--text-tertiary); display: inline-flex; font-size: 0.72rem; font-weight: 680; gap: 0.32rem; }
.chat-transcript__row--user .chat-transcript__content { justify-items: end; }
.chat-transcript__row--user .chat-transcript__role { flex-direction: row-reverse; }
.chat-transcript__bubble { border-radius: 1rem; padding: 0.85rem 1.05rem; width: fit-content; }
.chat-transcript__bubble--assistant { background: #fbfcfc; border: 1px solid var(--line); border-bottom-left-radius: 0.3rem; box-shadow: 0 1px 2px rgb(16 24 40 / 5%), 0 6px 20px rgb(16 24 40 / 3%); max-width: 100%; min-width: 0; }
.chat-transcript__bubble--user { background: var(--accent-soft); border: 1px solid var(--accent-border); border-bottom-right-radius: 0.3rem; max-width: min(34rem, 100%); }
.chat-transcript__message p { line-height: 1.7; margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; word-break: break-word; }
.chat-transcript__bubble--user p { color: #14443a; }
.chat-transcript__typing { display: inline-flex; gap: 0.3rem; padding: 0.4rem 0 0.1rem; }
.chat-transcript__typing span { animation: chat-typing 1.2s ease-in-out infinite; background: var(--accent); border-radius: 50%; height: 0.42rem; width: 0.42rem; }
.chat-transcript__typing span:nth-child(2) { animation-delay: 0.16s; }
.chat-transcript__typing span:nth-child(3) { animation-delay: 0.32s; }
@keyframes chat-typing { 0%, 60%, 100% { opacity: 0.25; transform: translateY(0); } 30% { opacity: 0.9; transform: translateY(-0.15rem); } }
.chat-transcript__message-sources { border-top: 1px dashed var(--accent-border); display: grid; gap: 0.55rem; list-style: none; margin: 0.85rem 0 0; padding: 0.75rem 0 0; }
.chat-transcript__message-sources li { display: grid; gap: 0.35rem; justify-items: start; }
.chat-transcript__message-sources li button { align-items: center; background: var(--accent-soft); border: 1px solid var(--accent-border); border-radius: 999px; color: var(--accent-strong); display: inline-flex; font-size: 0.74rem; font-weight: 600; gap: 0.3rem; padding: 0.28rem 0.55rem; transition: background var(--transition-fast), border-color var(--transition-fast); }
.chat-transcript__message-sources li button:hover { background: #d7f0e7; border-color: #8fd3bf; }
.chat-transcript__message-footer { border-top: 1px solid var(--line); margin-top: 0.75rem; padding-top: 0.55rem; }
.chat-transcript__details { border-top: 1px solid var(--line); color: var(--text-secondary); font-size: 0.78rem; margin-top: 0.7rem; padding-top: 0.5rem; }
.chat-transcript__details summary { align-items: center; border-radius: var(--radius-sm); cursor: pointer; display: flex; font-weight: 700; gap: 0.35rem; list-style: none; padding: 0.3rem 0.45rem; transition: background var(--transition-fast); }
.chat-transcript__details summary::-webkit-details-marker { display: none; }
.chat-transcript__details summary:hover { background: var(--surface-hover); }
.chat-transcript__details summary svg { color: var(--accent-strong); }
.chat-transcript__details ul { display: grid; gap: 0.4rem; list-style: none; margin: 0.55rem 0 0.15rem; padding: 0 0.45rem 0.2rem; }
.chat-transcript__details li { align-items: center; background: var(--surface-inset); border-radius: var(--radius-sm); display: grid; gap: 0.45rem; grid-template-columns: minmax(0, 1fr) auto; padding: 0.45rem 0.6rem; }
.chat-transcript__details li span { font-weight: 600; }
.chat-transcript__details li small { color: var(--text-tertiary); grid-column: 1 / -1; overflow-wrap: anywhere; }
.chat-transcript__details p { color: var(--text-secondary); font-size: 0.78rem; line-height: 1.6; margin: 0.55rem 0 0.2rem; padding: 0 0.45rem 0.2rem; white-space: pre-wrap; }
.chat-transcript__context { background: #fbfbfc; border: 1px solid var(--line); border-radius: var(--radius-md); max-width: 46rem; padding: 0.9rem 1rem; }
h2 { align-items: center; color: var(--text-secondary); display: flex; font-size: 0.78rem; font-weight: 700; gap: 0.42rem; margin: 0 0 0.7rem; }
.chat-transcript__context ul { display: grid; gap: 0.42rem; list-style: none; margin: 0; padding: 0; }
.chat-transcript__context li { display: grid; gap: 0.45rem; }
.chat-transcript__reference-heading { align-items: center; display: grid; gap: 0.5rem; grid-template-columns: auto minmax(0, 1fr); }
.chat-transcript__reference-heading > span { color: var(--text-tertiary); font-size: 0.7rem; }
.chat-transcript__reference-heading > button { font-size: 0.81rem; font-weight: 650; overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.chat-transcript__reference-heading > button:hover { color: var(--accent-strong); text-decoration: underline; }
.chat-transcript__context li > span { align-items: center; display: grid; font-size: 0.81rem; gap: 0.25rem; grid-template-columns: auto minmax(0, 1fr); }
.chat-transcript__context li > span small { color: var(--text-secondary); font-size: 0.74rem; grid-column: 1 / -1; overflow-wrap: anywhere; }
.chat-transcript__context li > span svg { color: var(--accent-strong); }
.chat-transcript__context li > span svg + * { min-width: 0; }
@media (max-width: 860px) { .chat-transcript { overflow-y: visible; } }
@media (max-width: 640px) { .chat-transcript { padding: 1.15rem 0; } .chat-transcript__message { max-width: 96%; } .chat-transcript__bubble--user { max-width: 100%; } }
</style>
