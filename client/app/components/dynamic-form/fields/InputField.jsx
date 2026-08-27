import React from "react";
import Input from "antd/lib/input";

export default function InputField({ form, field, ...otherProps }) {
  if (otherProps.type === "password") {
    const { type, ...passwordProps } = otherProps;
    return <Input.Password {...passwordProps} />;
  }

  return <Input {...otherProps} />;
}
