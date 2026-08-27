import { get, map } from "lodash";
import React, { useMemo, useCallback, useState } from "react";
import PropTypes from "prop-types";
import Button from "antd/lib/button";
import { UserProfile } from "@/components/proptypes";
import DynamicComponent from "@/components/DynamicComponent";
import DynamicForm from "@/components/dynamic-form/DynamicForm";
import UserGroups from "@/components/UserGroups";

import User from "@/services/user";
import { currentUser } from "@/services/auth";
import useImmutableCallback from "@/lib/hooks/useImmutableCallback";

import useUserGroups from "../hooks/useUserGroups";

export default function UserInfoForm(props) {
  const { user, onChange } = props;
  const [authorizing, setAuthorizing] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const { groups, allGroups, isLoading: isLoadingGroups } = useUserGroups(user);

  const handleChange = useImmutableCallback(onChange);

  const saveUser = useCallback(
    (values, successCallback, errorCallback) => {
      const { password, password_confirm: passwordConfirm, ...rest } = values;
      const data = {
        ...rest,
        id: user.id,
      };

      if (password || passwordConfirm) {
        if (!password || password.length < 6) {
          errorCallback("Password is too short.");
          return;
        }
        if (password !== passwordConfirm) {
          errorCallback("Passwords don't match.");
          return;
        }
        data.password = password;
      }

      User.save(data)
        .then(savedUser => {
          successCallback("Saved.");
          handleChange(User.convertUserInfo(savedUser));
          setFormKey(key => key + 1);
        })
        .catch(error => {
          errorCallback(get(error, "response.data.message", "Failed saving."));
        });
    },
    [user, handleChange]
  );

  const authorizeUser = useCallback(() => {
    setAuthorizing(true);
    User.authorizeUser(user)
      .then(data => {
        if (data) {
          handleChange(User.convertUserInfo(data));
        }
      })
      .finally(() => {
        setAuthorizing(false);
      });
  }, [user, handleChange]);

  const formFields = useMemo(
    () =>
      map(
        [
          {
            name: "name",
            title: "Name",
            type: "text",
            initialValue: user.name,
          },
          {
            name: "email",
            title: "Email",
            type: "email",
            initialValue: user.email,
          },
          !user.isDisabled && currentUser.id !== user.id
            ? {
                name: "group_ids",
                title: "Groups",
                type: "select",
                mode: "multiple",
                options: map(allGroups, group => ({ name: group.name, value: group.id })),
                initialValue: user.groupIds,
                loading: isLoadingGroups,
                placeholder: isLoadingGroups ? "Loading..." : "",
              }
            : {
                name: "group_ids",
                title: "Groups",
                type: "content",
                required: false,
                content: isLoadingGroups ? "Loading..." : <UserGroups data-test="Groups" groups={groups} />,
              },
          !user.isDisabled &&
            currentUser.isAdmin &&
            currentUser.id !== user.id && {
              name: "password",
              title: "Password",
              type: "password",
              required: false,
              initialValue: "",
            },
          !user.isDisabled &&
            currentUser.isAdmin &&
            currentUser.id !== user.id && {
              name: "password_confirm",
              title: "Password Confirm",
              type: "password",
              required: false,
              initialValue: "",
            },
        ].filter(Boolean),
        field => ({ readOnly: user.isDisabled, required: true, ...field })
      ),
    [user, groups, allGroups, isLoadingGroups]
  );

  const showAuthorize = currentUser.isAdmin && user.isInvitationPending && !user.isDisabled;

  return (
    <DynamicComponent name="UserProfile.UserInfoForm" {...props}>
      <DynamicForm key={formKey} fields={formFields} onSubmit={saveUser} hideSubmitButton={user.isDisabled} />
      {showAuthorize && (
        <Button className="w-100 m-t-10" type="primary" onClick={authorizeUser} loading={authorizing}>
          Authorize
        </Button>
      )}
    </DynamicComponent>
  );
}

UserInfoForm.propTypes = {
  user: UserProfile.isRequired,
  onChange: PropTypes.func,
};

UserInfoForm.defaultProps = {
  onChange: () => {},
};
