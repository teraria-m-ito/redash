import React, { useState, useCallback } from "react";
import PropTypes from "prop-types";
import Button from "antd/lib/button";
import Modal from "antd/lib/modal";
import DynamicComponent from "@/components/DynamicComponent";
import { UserProfile } from "@/components/proptypes";
import { currentUser } from "@/services/auth";
import User from "@/services/user";
import navigateTo from "@/components/ApplicationArea/navigateTo";
import useImmutableCallback from "@/lib/hooks/useImmutableCallback";

export default function ToggleUserForm(props) {
  const { user, onChange } = props;

  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const handleChange = useImmutableCallback(onChange);

  const toggleUser = useCallback(() => {
    const action = user.isDisabled ? User.enableUser : User.disableUser;
    setLoading(true);
    action(user)
      .then(data => {
        if (data) {
          handleChange(User.convertUserInfo(data));
        }
      })
      .finally(() => {
        setLoading(false);
      });
  }, [user, handleChange]);

  const deleteUser = useCallback(() => {
    Modal.confirm({
      title: "Delete User",
      content: `Are you sure you want to delete ${user.name}? This cannot be undone.`,
      okText: "Delete",
      okType: "danger",
      onOk: () => {
        setDeleting(true);
        return User.deleteUser(user)
          .then(data => {
            if (data !== undefined) {
              navigateTo("users");
            }
          })
          .finally(() => {
            setDeleting(false);
          });
      },
      maskClosable: true,
      autoFocusButton: null,
    });
  }, [user]);

  if (!currentUser.isAdmin || user.id === currentUser.id) {
    return null;
  }

  const buttonProps = {
    type: user.isDisabled ? "primary" : "danger",
    children: user.isDisabled ? "Enable User" : "Disable User",
  };

  return (
    <DynamicComponent name="UserProfile.ToggleUserForm">
      <Button className="w-100 m-t-10" onClick={toggleUser} loading={loading} {...buttonProps} />
      {user.isDisabled && (
        <Button className="w-100 m-t-10" type="danger" onClick={deleteUser} loading={deleting}>
          Delete User
        </Button>
      )}
    </DynamicComponent>
  );
}

ToggleUserForm.propTypes = {
  user: UserProfile.isRequired,
  onChange: PropTypes.func,
};

ToggleUserForm.defaultProps = {
  onChange: () => {},
};
