import React from "react";
import PropTypes from "prop-types";
import Input from "antd/lib/input";
import { getDefaultName } from "../Insight";

import "@/pages/alert/components/Title.less";

export default function Title({ insight, editMode, name, onChange, children }) {
  const defaultName = getDefaultName(insight);
  return (
    <div className="alert-header">
      <div className="alert-title">
        <h3>
          {editMode && insight.query ? (
            <Input
              className="f-inherit"
              placeholder={defaultName}
              value={name}
              aria-label="Insight title"
              onChange={e => onChange(e.target.value)}
            />
          ) : (
            name || defaultName
          )}
        </h3>
      </div>
      <div className="alert-actions">{children}</div>
    </div>
  );
}

Title.propTypes = {
  insight: PropTypes.object.isRequired, // eslint-disable-line react/forbid-prop-types
  name: PropTypes.string,
  children: PropTypes.node,
  onChange: PropTypes.func,
  editMode: PropTypes.bool,
};

Title.defaultProps = {
  name: null,
  children: null,
  onChange: null,
  editMode: false,
};
