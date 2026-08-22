import React from "react";
import PropTypes from "prop-types";

import Form from "antd/lib/form";
import Button from "antd/lib/button";

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
    const { onQuerySelected, onNameChange, onColumnsChange } = this.props;
    const { query, name, options } = insight;
    const { saving } = this.state;

    return (
      <>
        <Title insight={insight} name={name} onChange={onNameChange} editMode />
        <div className="bg-white tiled p-20">
          <Form className="flex-fill">
            <div className="m-b-30">
              Start by selecting the query that you would like to analyze with AI.
              <br />
              Keep in mind that Insights work best with queries that have a refresh schedule.
            </div>
            <HorizontalFormItem label="Query">
              <Query query={query} queryResult={queryResult} onChange={onQuerySelected} editMode />
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
              <Button
                type="primary"
                onClick={this.save}
                disabled={!query || !options.dimension_column || !options.category_column}
                className="btn-create-insight">
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
  onQuerySelected: PropTypes.func.isRequired,
  save: PropTypes.func.isRequired,
  onNameChange: PropTypes.func.isRequired,
  onColumnsChange: PropTypes.func.isRequired,
};

InsightNew.defaultProps = {
  queryResult: null,
};
