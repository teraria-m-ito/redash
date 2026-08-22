import React from "react";
import PropTypes from "prop-types";

import Form from "antd/lib/form";
import Button from "antd/lib/button";

import Query from "@/pages/alert/components/Query";
import HorizontalFormItem from "@/pages/alert/components/HorizontalFormItem";

import Title from "./components/Title";
import ColumnMapping from "./components/ColumnMapping";

export default class InsightEdit extends React.Component {
  _isMounted = false;

  state = {
    saving: false,
  };

  componentDidMount() {
    this._isMounted = true;
  }

  componentWillUnmount() {
    this._isMounted = false;
  }

  save = () => {
    this.setState({ saving: true });
    this.props.save().catch(() => {
      if (this._isMounted) {
        this.setState({ saving: false });
      }
    });
  };

  cancel = () => {
    this.props.cancel();
  };

  render() {
    const { insight, queryResult, menuButton } = this.props;
    const { onQuerySelected, onNameChange, onColumnsChange } = this.props;
    const { query, name, options } = insight;
    const { saving } = this.state;

    return (
      <>
        <Title name={name} insight={insight} onChange={onNameChange} editMode>
          <Button className="m-r-5" onClick={() => this.cancel()}>
            <i className="fa fa-times m-r-5" aria-hidden="true" />
            Cancel
          </Button>
          <Button type="primary" onClick={() => this.save()}>
            {saving ? (
              <span role="status" aria-live="polite" aria-relevant="additions removals">
                <i className="fa fa-spinner fa-pulse m-r-5" aria-hidden="true" />
                <span className="sr-only">Saving...</span>
              </span>
            ) : (
              <>
                <i className="fa fa-check m-r-5" aria-hidden="true" />
              </>
            )}
            Save Changes
          </Button>
          {menuButton}
        </Title>
        <div className="bg-white tiled p-20">
          <Form className="flex-fill">
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
          </Form>
        </div>
      </>
    );
  }
}

InsightEdit.propTypes = {
  insight: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  queryResult: PropTypes.object, // eslint-disable-line react/forbid-prop-types
  menuButton: PropTypes.node.isRequired,
  save: PropTypes.func.isRequired,
  cancel: PropTypes.func.isRequired,
  onQuerySelected: PropTypes.func.isRequired,
  onNameChange: PropTypes.func.isRequired,
  onColumnsChange: PropTypes.func.isRequired,
};

InsightEdit.defaultProps = {
  queryResult: null,
};
