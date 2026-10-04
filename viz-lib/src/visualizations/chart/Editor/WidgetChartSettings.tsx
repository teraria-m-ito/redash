import { isNil } from "lodash";
import React from "react";
import { Section, Switch, TextArea } from "@/components/visualizations/editor";
import { EditorPropTypes } from "@/visualizations/prop-types";
import {
  DEFAULT_WIDGET_CSS,
  DEFAULT_WIDGET_HTML,
  DEFAULT_WIDGET_JS,
} from "../widgetDefaults";

export default function WidgetChartSettings({ options, onOptionsChange }: any) {
  return (
    <React.Fragment>
      {/* @ts-expect-error ts-migrate(2745) FIXME: This JSX tag's 'children' prop expects type 'never... Remove this comment to see the full error message */}
      <Section>
        <TextArea
          label="HTML"
          data-test="Chart.Widget.Html"
          rows="8"
          defaultValue={isNil(options.widgetHtml) ? DEFAULT_WIDGET_HTML : options.widgetHtml}
          onChange={(event: any) => onOptionsChange({ widgetHtml: event.target.value })}
        />
      </Section>

      {/* @ts-expect-error ts-migrate(2745) FIXME: This JSX tag's 'children' prop expects type 'never... Remove this comment to see the full error message */}
      <Section>
        <TextArea
          label="CSS"
          data-test="Chart.Widget.Css"
          rows="6"
          defaultValue={isNil(options.widgetCss) ? DEFAULT_WIDGET_CSS : options.widgetCss}
          onChange={(event: any) => onOptionsChange({ widgetCss: event.target.value })}
        />
      </Section>

      {/* @ts-expect-error ts-migrate(2745) FIXME: This JSX tag's 'children' prop expects type 'never... Remove this comment to see the full error message */}
      <Section>
        <TextArea
          label="JavaScript"
          data-test="Chart.Widget.Js"
          rows="10"
          defaultValue={isNil(options.widgetJs) ? DEFAULT_WIDGET_JS : options.widgetJs}
          onChange={(event: any) => onOptionsChange({ widgetJs: event.target.value })}
        />
      </Section>

      {/* @ts-expect-error ts-migrate(2745) FIXME: This JSX tag's 'children' prop expects type 'never... Remove this comment to see the full error message */}
      <Section>
        {/* @ts-expect-error ts-migrate(2745) FIXME: This JSX tag's 'children' prop expects type 'never... Remove this comment to see the full error message */}
        <Switch
          data-test="Chart.Widget.EnableConsoleLogs"
          // @ts-expect-error ts-migrate(2322) FIXME: Type 'any' is not assignable to type 'never'.
          defaultChecked={options.enableConsoleLogs}
          // @ts-expect-error ts-migrate(2322) FIXME: Type '(enableConsoleLogs: any) => any' is not assi... Remove this comment to see the full error message
          onChange={(enableConsoleLogs: any) => onOptionsChange({ enableConsoleLogs })}>
          Show errors in the console
        </Switch>
      </Section>
    </React.Fragment>
  );
}

WidgetChartSettings.propTypes = EditorPropTypes;
