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

  const { groups, allGroups, isLoading: isLoadingGroups } = useUserGroups(user);

  const handleChange = useImmutableCallback(onChange);

  const saveUser = useCallback(
    (values, successCallback, errorCallback) => {
      const data = {
        ...values,
        id: user.id,
      };

      User.save(data)
        .then(user => {
          successCallback("Saved.");
          handleChange(User.convertUserInfo(user));
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
        ],
        field => ({ readOnly: user.isDisabled, required: true, ...field })
      ),
    [user, groups, allGroups, isLoadingGroups]
  );

  const showAuthorize = currentUser.isAdmin && user.isInvitationPending && !user.isDisabled;

  return (
    <DynamicComponent name="UserProfile.UserInfoForm" {...props}>
      <DynamicForm fields={formFields} onSubmit={saveUser} hideSubmitButton={user.isDisabled} />
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
