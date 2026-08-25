import React from "react";
import PropTypes from "prop-types";

import Link from "@/components/Link";
import QuerySelector from "@/components/QuerySelector";
import SchedulePhrase from "@/components/queries/SchedulePhrase";
import { Query as QueryType } from "@/components/proptypes";

import Tooltip from "@/components/Tooltip";

import WarningFilledIcon from "@ant-design/icons/WarningFilled";
import QuestionCircleTwoToneIcon from "@ant-design/icons/QuestionCircleTwoTone";
import LoadingOutlinedIcon from "@ant-design/icons/LoadingOutlined";

import "./Query.less";

export default function QueryFormItem({ query, queryResult, onChange, editMode, isLoadingQueryResult, queryResultError }) {
  const queryHint =
    query && query.schedule ? (
      <small>
        Scheduled to refresh{" "}
        <i className="alert-query-schedule">
          <SchedulePhrase schedule={query.schedule} isNew={false} />
        </i>
      </small>
    ) : (
      <small>
        <WarningFilledIcon className="warning-icon-danger" /> This query has no <i>refresh schedule</i>.{" "}
        <Tooltip title="A query schedule is not necessary but is highly recommended for alerts. An Alert without a query schedule will only send notifications if a user in your organization manually executes this query.">
          <a role="presentation">
            Why it&apos;s recommended <QuestionCircleTwoToneIcon />
          </a>
        </Tooltip>
      </small>
    );

  // Alerts omit isLoadingQueryResult (undefined) and keep previous loading behavior
  const showLoading =
    query && !queryResult && !queryResultError && (isLoadingQueryResult == null ? true : isLoadingQueryResult);

  return (
    <>
      {editMode ? (
        <QuerySelector onChange={onChange} selectedQuery={query} className="alert-query-selector" type="select" />
      ) : (
        <Tooltip title="Open query in a new tab.">
          <Link href={`queries/${query.id}`} target="_blank" rel="noopener noreferrer" className="alert-query-link">
            {query.name} <i className="fa fa-external-link" aria-hidden="true" />
            <span className="sr-only">(opens in a new tab)</span>
          </Link>
        </Tooltip>
      )}
      <div className="ant-form-item-explain">{query && queryHint}</div>
      {showLoading && (
        <div className="m-t-30">
          <LoadingOutlinedIcon className="m-r-5" /> Loading query data
        </div>
      )}
      {query && queryResultError && !queryResult && (
        <div className="m-t-30">
          <WarningFilledIcon className="warning-icon-danger m-r-5" /> {queryResultError}
        </div>
      )}
    </>
  );
}

QueryFormItem.propTypes = {
  query: QueryType,
  queryResult: PropTypes.object, // eslint-disable-line react/forbid-prop-types
  onChange: PropTypes.func,
  editMode: PropTypes.bool,
  isLoadingQueryResult: PropTypes.bool,
  queryResultError: PropTypes.string,
};

QueryFormItem.defaultProps = {
  query: null,
  queryResult: null,
  onChange: () => {},
  editMode: false,
  // Alerts keep previous behavior: show loading whenever query is set without result
  isLoadingQueryResult: undefined,
  queryResultError: null,
};
