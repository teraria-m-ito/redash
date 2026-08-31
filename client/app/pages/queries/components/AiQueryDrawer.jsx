import { get } from "lodash";
import React, { useCallback, useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import Button from "antd/lib/button";
import Drawer from "antd/lib/drawer";
import Input from "antd/lib/input";
import Spin from "antd/lib/spin";
import Link from "@/components/Link";
import { currentUser } from "@/services/auth";
import notification from "@/services/notification";
import AiQuery from "@/services/aiQuery";

import "./AiQueryDrawer.less";

export const AiMessageRole = {
  USER: "user",
  ASSISTANT: "assistant",
};

function getErrorMessage(error) {
  return (
    get(error, "response.data.message") ||
    get(error, "response.data.error") ||
    get(error, "response.statusText") ||
    get(error, "message") ||
    "クエリの生成に失敗しました。"
  );
}

export default function AiQueryDrawer({
  visible,
  currentQuery,
  dataSourceId,
  schema,
  syntax,
  onClose,
  onApplyQuery,
}) {
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [sqlPairs, setSqlPairs] = useState([]);
  const [instructions, setInstructions] = useState([]);
  const [savingPairKey, setSavingPairKey] = useState(null);
  const [instructionTitle, setInstructionTitle] = useState("");
  const [instructionContent, setInstructionContent] = useState("");
  const [isSavingInstruction, setIsSavingInstruction] = useState(false);
  const listRef = useRef(null);

  const loadKnowledge = useCallback(() => {
    if (!dataSourceId) {
      setSqlPairs([]);
      setInstructions([]);
      return Promise.resolve();
    }
    return Promise.all([AiQuery.listSqlPairs(dataSourceId), AiQuery.listInstructions(dataSourceId)])
      .then(([pairs, rules]) => {
        setSqlPairs(pairs || []);
        setInstructions(rules || []);
      })
      .catch(() => {
        setSqlPairs([]);
        setInstructions([]);
      });
  }, [dataSourceId]);

  useEffect(() => {
    if (visible) {
      loadKnowledge();
    }
  }, [visible, loadKnowledge]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isGenerating, visible]);

  const sendPrompt = useCallback(() => {
    const text = prompt.trim();
    if (!text || isGenerating) {
      return;
    }

    const history = messages.map(item => ({ role: item.role, content: item.content }));
    setPrompt("");
    setMessages(current => [...current, { role: AiMessageRole.USER, content: text }]);
    setIsGenerating(true);

    AiQuery.generateQuery({
      prompt: text,
      messages: history,
      current_query: currentQuery || "",
      data_source_id: dataSourceId,
      schema,
      syntax: syntax || "sql",
      validate: Boolean(dataSourceId),
      use_reasoning: true,
    })
      .then(data => {
        const queryText = data.query || "";
        let message = data.message || "クエリを生成しました。";
        if (data.validated) {
          message = `${message}（検証済み）`;
        }
        setMessages(current => [
          ...current,
          {
            role: AiMessageRole.ASSISTANT,
            content: message,
            query: queryText,
            question: text,
            validated: data.validated,
            reasoning: data.reasoning,
          },
        ]);
      })
      .catch(error => {
        const errorMessage = getErrorMessage(error);
        notification.error(errorMessage);
        setMessages(current => [...current, { role: AiMessageRole.ASSISTANT, content: errorMessage, isError: true }]);
      })
      .finally(() => setIsGenerating(false));
  }, [prompt, isGenerating, messages, currentQuery, dataSourceId, schema, syntax]);

  const saveSqlPair = useCallback(
    (question, query, messageKey) => {
      if (!dataSourceId || !question || !query) {
        return;
      }
      setSavingPairKey(messageKey);
      AiQuery.createSqlPair({
        data_source_id: dataSourceId,
        question,
        query,
      })
        .then(() => {
          notification.success("SQL例を保存しました。");
          loadKnowledge();
        })
        .catch(error => notification.error(getErrorMessage(error)))
        .finally(() => setSavingPairKey(null));
    },
    [dataSourceId, loadKnowledge]
  );

  const deleteSqlPair = useCallback(
    pairId => {
      AiQuery.deleteSqlPair(pairId)
        .then(() => {
          notification.success("SQL例を削除しました。");
          loadKnowledge();
        })
        .catch(error => notification.error(getErrorMessage(error)));
    },
    [loadKnowledge]
  );

  const saveInstruction = useCallback(() => {
    const content = instructionContent.trim();
    if (!dataSourceId || !content || isSavingInstruction) {
      return;
    }
    setIsSavingInstruction(true);
    AiQuery.createInstruction({
      data_source_id: dataSourceId,
      title: instructionTitle.trim() || undefined,
      content,
    })
      .then(() => {
        notification.success("ビジネスルールを保存しました。");
        setInstructionTitle("");
        setInstructionContent("");
        loadKnowledge();
      })
      .catch(error => notification.error(getErrorMessage(error)))
      .finally(() => setIsSavingInstruction(false));
  }, [dataSourceId, instructionContent, instructionTitle, isSavingInstruction, loadKnowledge]);

  const deleteInstruction = useCallback(
    instructionId => {
      AiQuery.deleteInstruction(instructionId)
        .then(() => {
          notification.success("ビジネスルールを削除しました。");
          loadKnowledge();
        })
        .catch(error => notification.error(getErrorMessage(error)));
    },
    [loadKnowledge]
  );

  return (
    <Drawer
      title="AI Query"
      placement="right"
      visible={visible}
      onClose={onClose}
      width={420}
      className="ai-query-drawer"
      destroyOnClose={false}>
      <div className="ai-query-drawer-body">
        <div className="ai-query-drawer-messages" ref={listRef}>
          {messages.length === 0 && (
            <div className="ai-query-drawer-empty">
              作りたいクエリを日本語で入力してください。関連テーブルとビジネスルールを参照して生成します。
              {schema.length > 0 && <div className="m-t-10">読み込み済みテーブル: {schema.length} 件</div>}
              {schema.length === 0 && (
                <div className="m-t-10">スキーマ未取得です。左ペインのテーブル一覧が表示されてから送信してください。</div>
              )}
              {dataSourceId && sqlPairs.length > 0 && (
                <div className="m-t-10">登録済み SQL 例: {sqlPairs.length} 件</div>
              )}
              {dataSourceId && instructions.length > 0 && (
                <div className="m-t-10">登録済みビジネスルール: {instructions.length} 件</div>
              )}
              {currentUser.isAdmin && (
                <div className="m-t-10">
                  接続設定は <Link href="settings/ai">AI Setting</Link> で行います。
                </div>
              )}
            </div>
          )}
          {messages.map((item, index) => {
            const messageKey = `ai-message-${index}`;
            return (
              <div
                key={messageKey}
                className={`ai-query-drawer-message ai-query-drawer-message-${item.role}${
                  item.isError ? " ai-query-drawer-message-error" : ""
                }`}>
                <div className="ai-query-drawer-message-content">{item.content}</div>
                {item.reasoning && (
                  <pre className="ai-query-drawer-reasoning">{item.reasoning}</pre>
                )}
                {item.query && (
                  <React.Fragment>
                    <pre className="ai-query-drawer-query">{item.query}</pre>
                    <div className="ai-query-drawer-actions m-t-5">
                      <Button data-test="AiQueryApplyButton" onClick={() => onApplyQuery(item.query)}>
                        Apply
                      </Button>
                      {dataSourceId && item.question && (
                        <Button
                          className="m-l-5"
                          loading={savingPairKey === messageKey}
                          onClick={() => saveSqlPair(item.question, item.query, messageKey)}>
                          例として保存
                        </Button>
                      )}
                    </div>
                  </React.Fragment>
                )}
              </div>
            );
          })}
          {isGenerating && (
            <div className="ai-query-drawer-loading">
              <Spin size="small" /> クエリを生成しています...
            </div>
          )}
        </div>
        {dataSourceId && (
          <div className="ai-query-drawer-knowledge m-t-10">
            <div className="ai-query-drawer-pairs-title">ビジネスルール</div>
            {instructions.map(instruction => (
              <div key={instruction.id} className="ai-query-drawer-pair-item">
                <div className="ai-query-drawer-pair-question">
                  {instruction.title || instruction.content}
                </div>
                <Button size="small" danger onClick={() => deleteInstruction(instruction.id)}>
                  削除
                </Button>
              </div>
            ))}
            <Input
              className="m-t-5"
              value={instructionTitle}
              onChange={e => setInstructionTitle(e.target.value)}
              placeholder="ルール名（任意）"
              disabled={isSavingInstruction}
            />
            <Input.TextArea
              className="m-t-5"
              value={instructionContent}
              onChange={e => setInstructionContent(e.target.value)}
              placeholder="例: 売上は orders.amount の合計。status=4 は返金済みなので除外"
              autoSize={{ minRows: 2, maxRows: 4 }}
              disabled={isSavingInstruction}
            />
            <Button
              className="m-t-5"
              block
              loading={isSavingInstruction}
              disabled={!instructionContent.trim()}
              onClick={saveInstruction}>
              ルールを追加
            </Button>
            {sqlPairs.length > 0 && (
              <React.Fragment>
                <div className="ai-query-drawer-pairs-title m-t-15">SQL 例</div>
                {sqlPairs.slice(0, 5).map(pair => (
                  <div key={pair.id} className="ai-query-drawer-pair-item">
                    <div className="ai-query-drawer-pair-question">{pair.question}</div>
                    <Button size="small" danger onClick={() => deleteSqlPair(pair.id)}>
                      削除
                    </Button>
                  </div>
                ))}
              </React.Fragment>
            )}
          </div>
        )}
        <div className="ai-query-drawer-input">
          <Input.TextArea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="例: 月別の売上合計を出して"
            autoSize={{ minRows: 3, maxRows: 6 }}
            disabled={isGenerating}
            onPressEnter={e => {
              if (!e.shiftKey) {
                e.preventDefault();
                sendPrompt();
              }
            }}
            data-test="AiQueryPrompt"
          />
          <Button
            type="primary"
            className="m-t-10"
            block
            loading={isGenerating}
            disabled={!prompt.trim()}
            onClick={sendPrompt}
            data-test="AiQuerySendButton">
            送信
          </Button>
        </div>
      </div>
    </Drawer>
  );
}

AiQueryDrawer.propTypes = {
  visible: PropTypes.bool,
  currentQuery: PropTypes.string,
  dataSourceId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  schema: PropTypes.array,
  syntax: PropTypes.string,
  onClose: PropTypes.func,
  onApplyQuery: PropTypes.func,
};

AiQueryDrawer.defaultProps = {
  visible: false,
  currentQuery: "",
  dataSourceId: null,
  schema: [],
  syntax: "sql",
  onClose: () => {},
  onApplyQuery: () => {},
};
