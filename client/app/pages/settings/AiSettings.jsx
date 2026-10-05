import React from "react";
import PropTypes from "prop-types";

import Button from "antd/lib/button";
import Form from "antd/lib/form";
import Input from "antd/lib/input";
import InputNumber from "antd/lib/input-number";
import Skeleton from "antd/lib/skeleton";
import routeWithUserSession from "@/components/ApplicationArea/routeWithUserSession";
import wrapSettingsTab from "@/components/SettingsWrapper";

import routes from "@/services/routes";
import { getHorizontalFormProps, getHorizontalFormItemWithoutLabelProps } from "@/styles/formStyle";

import useOrganizationSettings from "./hooks/useOrganizationSettings";
import { SettingsEditorPropTypes, SettingsEditorDefaultProps } from "./components/prop-types";

const AiSettingKey = {
  API_URL: "ai_api_url",
  API_KEY: "ai_api_key",
  MODEL: "ai_model",
  TEMPERATURE: "ai_temperature",
};

const AiTemperature = {
  DEFAULT: 0.1,
  MIN: 0,
  MAX: 2,
  STEP: 0.1,
};

function ConnectionSettings({ values, onChange, loading }) {
  const aiEnabled = Boolean((values[AiSettingKey.API_URL] || "").trim());

  return (
    <React.Fragment>
      <h3 className="m-t-0">AI接続</h3>
      <p className="text-muted">
        AI Query や Insight などで利用する LLM の接続先を設定します。ChatGPT（OpenAI）と Ollama のいずれかを選んで入力してください。
      </p>
      <div className="text-muted m-b-15">
        <p className="m-b-10">
          <strong>ChatGPT（OpenAI）</strong>
          <br />
          API URL には <code>https://api.openai.com/v1</code> を入力します。APIキーには OpenAI の API キーを入力してください（必須）。モデル名には利用するモデル（例: <code>gpt-4o-mini</code>、<code>gpt-4o</code>）を入力します。
        </p>
        <p className="m-b-0">
          <strong>Ollama</strong>
          <br />
          API URL には Ollama サーバーのチャット API（例: <code>http://host:11434/api/chat</code>）を入力します。APIキーは不要なので空のままで構いません。モデル名には <code>ollama list</code> で表示される名前（例: <code>llama3.2</code>）を入力します。
        </p>
      </div>
      {!loading && (
        <p className={aiEnabled ? "text-muted m-b-15" : "text-warning m-b-15"}>
          {aiEnabled
            ? "API URL が設定されているため、AI Query / Insights を表示します。"
            : "API URL が未設定のため、保存後は AI Query / Insights を非表示にします。"}
        </p>
      )}
      <hr />
      <Form.Item label="API URL">
        {loading ? (
          <Skeleton.Input style={{ width: 400 }} active />
        ) : (
          <Input
            placeholder="https://api.openai.com/v1 または http://host:11434/api/chat"
            value={values[AiSettingKey.API_URL]}
            onChange={e => onChange({ [AiSettingKey.API_URL]: e.target.value })}
            data-test="AiApiUrl"
          />
        )}
      </Form.Item>
      <Form.Item label="APIキー">
        {loading ? (
          <Skeleton.Input style={{ width: 400 }} active />
        ) : (
          <Input.Password
            placeholder="ChatGPT: APIキー / Ollama: 空で可"
            value={values[AiSettingKey.API_KEY]}
            onChange={e => onChange({ [AiSettingKey.API_KEY]: e.target.value })}
            data-test="AiApiKey"
          />
        )}
      </Form.Item>
      <Form.Item label="モデル名">
        {loading ? (
          <Skeleton.Input style={{ width: 400 }} active />
        ) : (
          <Input
            placeholder="gpt-4o-mini または llama3.2"
            value={values[AiSettingKey.MODEL]}
            onChange={e => onChange({ [AiSettingKey.MODEL]: e.target.value })}
            data-test="AiModel"
          />
        )}
      </Form.Item>
      <Form.Item
        label="Temperature"
        extra={`応答のばらつきを指定します（${AiTemperature.MIN}〜${AiTemperature.MAX}）。小さいほど毎回同じ結果になりやすく、SQL 生成には低い値が向いています。既定値は ${AiTemperature.DEFAULT} です。`}>
        {loading ? (
          <Skeleton.Input style={{ width: 120 }} active />
        ) : (
          <InputNumber
            min={AiTemperature.MIN}
            max={AiTemperature.MAX}
            step={AiTemperature.STEP}
            value={values[AiSettingKey.TEMPERATURE] ?? AiTemperature.DEFAULT}
            onChange={value =>
              onChange({ [AiSettingKey.TEMPERATURE]: typeof value === "number" ? value : AiTemperature.DEFAULT })
            }
            data-test="AiTemperature"
          />
        )}
      </Form.Item>
    </React.Fragment>
  );
}

ConnectionSettings.propTypes = SettingsEditorPropTypes;
ConnectionSettings.defaultProps = SettingsEditorDefaultProps;

function AiSettings({ onError }) {
  const { currentValues, isLoading, isSaving, handleSubmit, handleChange } = useOrganizationSettings({ onError });
  return (
    <div className="row" data-test="AiSettings">
      <div className="m-r-20 m-l-20">
        <Form {...getHorizontalFormProps()} onFinish={handleSubmit}>
          <ConnectionSettings loading={isLoading} values={currentValues} onChange={handleChange} />
          <Form.Item {...getHorizontalFormItemWithoutLabelProps()}>
            {isLoading ? (
              <Skeleton.Button active />
            ) : (
              <Button type="primary" htmlType="submit" loading={isSaving} data-test="AiSettingsSaveButton">
                保存
              </Button>
            )}
          </Form.Item>
        </Form>
      </div>
    </div>
  );
}

AiSettings.propTypes = {
  onError: PropTypes.func,
};

AiSettings.defaultProps = {
  onError: () => {},
};

const AiSettingsPage = wrapSettingsTab(
  "Settings.AI",
  {
    permission: "admin",
    title: "AI Setting",
    path: "settings/ai",
    order: 7,
  },
  AiSettings
);

routes.register(
  "Settings.AI",
  routeWithUserSession({
    path: "/settings/ai",
    title: "AI Setting",
    render: pageProps => <AiSettingsPage {...pageProps} />,
  })
);
