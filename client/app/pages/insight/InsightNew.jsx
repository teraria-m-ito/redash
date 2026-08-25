import React from "react";
import PropTypes from "prop-types";
import { trim } from "lodash";

import Form from "antd/lib/form";
import Button from "antd/lib/button";
import Input from "antd/lib/input";

import Query from "@/pages/alert/components/Query";
import HorizontalFormItem from "@/pages/alert/components/HorizontalFormItem";

import Title from "./components/Title";
import ColumnMapping from "./components/ColumnMapping";

export default class InsightNew extends React.Component {
  state = {
    saving: false,
  };

  save = () => {
    this.setState({ saving: true });
    this.props.save().catch(() => {
      this.setState({ saving: false });
    });
  };

  render() {
    const { insight, queryResult } = this.props;
    const { onQuerySelected, onNameChange, onPerspectiveChange, onColumnsChange } = this.props;
    const { query, name, analysis_perspective: perspective, options } = insight;
    const { saving } = this.state;
    const hasName = !!trim(name);
    const hasPerspective = !!trim(perspective);
    const canCreate = hasName && hasPerspective && query && options.dimension_column && options.category_column;

    return (
      <>
        <Title insight={insight} name={name} editMode={false} />
        <div className="bg-white tiled p-20">
          <Form className="flex-fill">
            <div className="m-b-30">
              Start by entering an Insight name and analysis perspective, then select the query and columns to analyze.
              <br />
              Insights work best with queries that have a refresh schedule.
            </div>
            <HorizontalFormItem label="Name" required>
              <Input
                value={name || ""}
                placeholder="e.g. Detect sudden changes in sales by customer"
                onChange={e => onNameChange(e.target.value)}
                maxLength={255}
              />
            </HorizontalFormItem>
            <HorizontalFormItem label="Analysis Perspective" required>
              <Input.TextArea
                value={perspective || ""}
                placeholder={
                  "e.g. Detect sudden changes over Dimension (time), or large deviations compared with other Categories"
                }
                onChange={e => onPerspectiveChange(e.target.value)}
                autoSize={{ minRows: 3, maxRows: 8 }}
              />
              <div className="ant-form-item-explain m-t-5">
                <small>Saved to the database and used as AI analysis input. Describe what to look for.</small>
              </div>
            </HorizontalFormItem>
            <HorizontalFormItem label="Query">
              <Query
                query={query}
                queryResult={queryResult}
                onChange={onQuerySelected}
                editMode
                isLoadingQueryResult={this.props.isLoadingQueryResult}
                queryResultError={this.props.queryResultError}
              />
            </HorizontalFormItem>
            {queryResult && options && (
              <HorizontalFormItem label="Columns" className="alert-criteria">
                <ColumnMapping
                  columnNames={queryResult.getColumnNames()}
                  options={options}
                  onChange={onColumnsChange}
                  editMode
                />
              </HorizontalFormItem>
            )}
            <HorizontalFormItem>
              <Button type="primary" onClick={this.save} disabled={!canCreate} className="btn-create-insight">
                {saving && (
                  <span role="status" aria-live="polite" aria-relevant="additions removals">
                    <i className="fa fa-spinner fa-pulse m-r-5" aria-hidden="true" />
                    <span className="sr-only">Saving...</span>
                  </span>
                )}
                Create Insight
              </Button>
            </HorizontalFormItem>
          </Form>
        </div>
      </>
    );
  }
}

InsightNew.propTypes = {
  insight: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  queryResult: PropTypes.object, // eslint-disable-line react/forbid-prop-types
  isLoadingQueryResult: PropTypes.bool,
  queryResultError: PropTypes.string,
  onQuerySelected: PropTypes.func.isRequired,
  save: PropTypes.func.isRequired,
  onNameChange: PropTypes.func.isRequired,
  onPerspectiveChange: PropTypes.func.isRequired,
  onColumnsChange: PropTypes.func.isRequired,
};

InsightNew.defaultProps = {
  queryResult: null,
  isLoadingQueryResult: false,
  queryResultError: null,
};
