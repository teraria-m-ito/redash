import React from "react";
import PropTypes from "prop-types";

import Select from "antd/lib/select";

import "@/pages/alert/components/Criteria.less";
import "./ColumnMapping.less";

function DisabledInput({ children }) {
  return <div className="criteria-disabled-input">{children}</div>;
}

DisabledInput.propTypes = {
  children: PropTypes.node.isRequired,
};

export default function ColumnMapping({ columnNames, options, onChange, editMode }) {
  const fields = [
    {
      key: "dimension_column",
      label: "Dimension",
      hint: "主に時系列（日時）を表す列",
    },
    {
      key: "category_column",
      label: "Category",
      hint: "ユーザID・商品IDなど対象を表す列",
    },
    {
      key: "message_to_column",
      label: "message_to",
      hint: "Insightの対象（ユーザ名など）を表す列",
    },
  ];

  return (
    <div className="insight-column-mapping" data-test="InsightColumnMapping">
      <div className="insight-column-selects">
        {fields.map(field => (
          <div className="input-title" key={field.key}>
            <span className="input-label">{field.label}</span>
            {editMode ? (
              <Select
                className="insight-column-select"
                value={options[field.key] || undefined}
                placeholder="列を選択"
                onChange={value => onChange({ [field.key]: value })}
                dropdownMatchSelectWidth={false}
                allowClear={field.key === "message_to_column"}
              >
                {columnNames.map(name => (
                  <Select.Option key={name}>{name}</Select.Option>
                ))}
              </Select>
            ) : (
              <DisabledInput>{options[field.key] || "-"}</DisabledInput>
            )}
          </div>
        ))}
      </div>
      <div className="ant-form-item-explain">
        {fields.map(field => (
          <div key={field.key}>
            <small className="alert-criteria-hint">
              <strong>{field.label}</strong>: {field.hint}
            </small>
          </div>
        ))}
      </div>
    </div>
  );
}

ColumnMapping.propTypes = {
  columnNames: PropTypes.arrayOf(PropTypes.string).isRequired,
  options: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  onChange: PropTypes.func,
  editMode: PropTypes.bool,
};

ColumnMapping.defaultProps = {
  onChange: () => {},
  editMode: false,
};
