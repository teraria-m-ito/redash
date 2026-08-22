import React from "react";
import PropTypes from "prop-types";
import cx from "classnames";

import TimeAgo from "@/components/TimeAgo";

import Form from "antd/lib/form";
import Button from "antd/lib/button";
import Tooltip from "@/components/Tooltip";
import Table from "antd/lib/table";
import * as Grid from "antd/lib/grid";

import Query from "@/pages/alert/components/Query";
import HorizontalFormItem from "@/pages/alert/components/HorizontalFormItem";

import Title from "./components/Title";
import ColumnMapping from "./components/ColumnMapping";

export default class InsightView extends React.Component {
  render() {
    const { insight, queryResult, canEdit, onEdit, menuButton } = this.props;
    const { query, name, options, results } = insight;

    const resultColumns = [
      {
        title: "message_to",
        dataIndex: "message_to",
        key: "message_to",
        width: "15%",
      },
      {
        title: "Message",
        dataIndex: "message",
        key: "message",
      },
      {
        title: "Detected At",
        dataIndex: "execute_at",
        key: "execute_at",
        width: "20%",
        render: value => (value ? <TimeAgo date={value} /> : "-"),
      },
    ];

    return (
      <>
        <Title name={name} insight={insight}>
          {canEdit ? (
            <>
              <Button type="default" onClick={canEdit ? onEdit : null} className={cx({ disabled: !canEdit })}>
                <i className="fa fa-edit m-r-5" aria-hidden="true" />
                Edit
              </Button>
              {menuButton}
            </>
          ) : (
            <Tooltip title="You do not have sufficient permissions to edit this insight">
              <Button type="default" onClick={canEdit ? onEdit : null} className={cx({ disabled: !canEdit })}>
                <i className="fa fa-edit m-r-5" aria-hidden="true" />
                Edit
              </Button>
              {menuButton}
            </Tooltip>
          )}
        </Title>
        <div className="bg-white tiled p-20">
          <Grid.Row type="flex" gutter={16}>
            <Grid.Col span={24}>
              <Form className="flex-fill">
                <HorizontalFormItem label="Query">
                  <Query query={query} queryResult={queryResult} />
                </HorizontalFormItem>
                {queryResult && options && (
                  <HorizontalFormItem label="Columns" className="alert-criteria">
                    <ColumnMapping columnNames={queryResult.getColumnNames()} options={options} />
                  </HorizontalFormItem>
                )}
              </Form>
            </Grid.Col>
          </Grid.Row>
        </div>
        <div className="bg-white tiled p-20 m-t-15">
          <h4 className="m-b-15">Detected Insights</h4>
          <Table
            rowKey="id"
            size="middle"
            pagination={false}
            columns={resultColumns}
            dataSource={results || []}
            locale={{ emptyText: "No insights detected yet." }}
          />
        </div>
      </>
    );
  }
}

InsightView.propTypes = {
  insight: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  queryResult: PropTypes.object, // eslint-disable-line react/forbid-prop-types
  canEdit: PropTypes.bool.isRequired,
  onEdit: PropTypes.func.isRequired,
  menuButton: PropTypes.node.isRequired,
};

InsightView.defaultProps = {
  queryResult: null,
};
