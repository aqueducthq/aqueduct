import {
  faBell,
  faCircleUser,
  faDatabase,
  faMessage,
  faPlug,
  faShareNodes,
} from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { Avatar, Link, Menu, MenuItem, Typography } from '@mui/material';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useLocation } from 'react-router-dom';

import { handleFetchNotifications } from '../../reducers/notifications';
import { AppDispatch, RootState } from '../../stores/store';
import UserProfile from '../../utils/auth';
import { getPathPrefix } from '../../utils/getPathPrefix';
import {
  NotificationLogLevel,
  NotificationStatus,
} from '../../utils/notifications';
import NotificationsPopover from '../notifications/NotificationsPopover';
import styles from './menu-sidebar-styles.module.css';

export const MenuSidebarWidth = '200px';

export type SidebarButtonProps = {
  icon: React.ReactElement;
  text: string;
  selected?: boolean;
  numUpdates?: number;
};

const BUTTON_STYLE_OVERRIDE = {
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'center',
  cursor: 'pointer',
  justifyContent: 'left',
  paddingX: 1,
  width: '100%',
  maxWidth: '100%',
  textTransform: 'none',
} as const;

const SidebarButton: React.FC<SidebarButtonProps> = ({
  icon,
  text,
  numUpdates = 0,
  selected = false,
}) => {
  return (
    <Button
      sx={{
        my: 1,
        ...BUTTON_STYLE_OVERRIDE,
        bg: selected ? 'blue.800' : 'blue.900',
        fontSize: '20px',
        color: 'white',
        '&:hover': {
          backgroundColor: 'blue.800',
        },
        '&:disabled': {
          backgroundColor: 'blue.800',
          color: 'white',
        },
      }}
      disabled={selected}
      disableRipple
    >
      <Box
        sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        {icon}
      </Box>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          width: '100%',
          alignItems: 'center',
          justifyContent: 'start',
        }}
      >
        {text}
        <Box sx={{ display: 'flex', flexGrow: 1, flexDirection: 'row' }} />
        {!!numUpdates && (
          <Box className={styles['notification-alert']}>
            <Typography
              variant="body2"
              sx={{ fontSize: '12px', fontWeight: 'light', color: 'white' }}
            >
              {numUpdates}
            </Typography>
          </Box>
        )}
      </Box>
    </Button>
  );
};

/**
 * The `MenuSidebar` is the core sidebar that we include throughout our UI. It
 * is pinned on the left-hand side of every page in our UI, and it includes
 * information about the user that logged in and quick links to core
 * abstractions in our system (workflows, integrations, etc).
 */
const MenuSidebar: React.FC<{ user: UserProfile }> = ({ user }) => {
  const [anchorEl, setAnchorEl] = useState(null);
  const [userPopoverAnchorEl, setUserPopoverAnchorEl] = useState(null);
  const [currentPage, setCurrentPage] = useState(undefined);
  const dispatch: AppDispatch = useDispatch();
  const location = useLocation();

  const numUnreadNotifications = useSelector(
    (state: RootState) =>
      state.notificationsReducer.notifications.filter(
        (notification) =>
          notification.level !== NotificationLogLevel.Success &&
          notification.status === NotificationStatus.Unread
      ).length
  );

  useEffect(() => {
    setCurrentPage(location.pathname);

    if (user) {
      dispatch(handleFetchNotifications({ user }));
    }
  }, []);

  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleUserPopoverClick = (event: React.MouseEvent) => {
    setUserPopoverAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleCloseUserPopover = () => {
    setUserPopoverAnchorEl(null);
  };

  const open = Boolean(anchorEl);
  const notificationsPopoverId = open ? 'simple-popover' : undefined;

  const userPopoverOpen = Boolean(userPopoverAnchorEl);
  const userPopoverId = userPopoverOpen ? 'user-popover' : undefined;

  const avatar = user.picture ? (
    <Avatar
      className={styles['user-avatar']}
      sx={{ width: '24px', height: '24px' }}
      src={user.picture}
    />
  ) : (
    <Avatar
      className={styles['user-avatar']}
      sx={{ width: '24px', height: '24px' }}
    >
      {user.name !== 'aqueduct user' ? user.name : null}
    </Avatar>
  );

  const sidebarContent = (
    <>
      <Box className={styles['menu-sidebar-popover-container']}>
        <Link href={`${getPathPrefix() ?? '/'}`} underline="none">
          <img
            style={{ maxWidth: '130px', width: '130px' }}
            src="https://aqueduct-public-assets-bucket.s3.us-east-2.amazonaws.com/webapp/logos/aqueduct_logo_horizontal.png"
          />
        </Link>

        {/* popover target */}
        <Button
          sx={{
            ...BUTTON_STYLE_OVERRIDE,
            mt: 2,
            mb: 1,
            height: '40px',
            backgroundColor: 'gray.100',
            color: 'darkGray',
            '&:hover': {
              backgroundColor: 'gray.300',
            },
            alignItems: 'center',
          }}
          onClick={handleUserPopoverClick}
          disableRipple
        >
          {avatar}
          <Box
            sx={{
              textOverflow: 'clip',
              whiteSpace: 'nowrap',
              display: 'block',
              overflow: 'hidden',
              width: '130px',
              maxWidth: '130px',
              fontSize: '16px',
              ml: 1,
            }}
          >
            {user.name === 'aqueduct user' ? 'Aqueduct' : user.name}
          </Box>
        </Button>
        {/* end popover target */}

        <Menu
          id={userPopoverId}
          anchorEl={userPopoverAnchorEl}
          onClose={handleCloseUserPopover}
          open={userPopoverOpen}
        >
          <Link
            href={`${getPathPrefix()}/account`}
            underline="none"
            sx={{ color: 'blue.800' }}
          >
            <MenuItem sx={{ width: '190px' }} disableRipple>
              <Box sx={{ fontSize: '20px', mr: 1 }}>
                <FontAwesomeIcon icon={faCircleUser} />
              </Box>
              Account
            </MenuItem>
          </Link>
        </Menu>
      </Box>

      <Box className={styles['menu-sidebar-links']}>
        <Box className={styles['menu-sidebar-links-wrapper']}>
          <Box className={styles['menu-sidebar-link']} onClick={handleClick}>
            <SidebarButton
              icon={
                <FontAwesomeIcon
                  className={styles['menu-sidebar-icon']}
                  icon={faBell}
                />
              }
              text="Notifications"
              numUpdates={numUnreadNotifications}
            />
          </Box>

          <NotificationsPopover
            user={user}
            id={notificationsPopoverId}
            anchorEl={anchorEl}
            handleClose={handleClose}
            open={open}
          />

          <Link
            href={`${getPathPrefix()}/workflows`}
            className={styles['menu-sidebar-link']}
            underline="none"
          >
            <SidebarButton
              icon={
                <FontAwesomeIcon
                  className={styles['menu-sidebar-icon']}
                  icon={faShareNodes}
                />
              }
              text="Workflows"
              selected={currentPage === '/workflows'}
            />
          </Link>

          <Link
            href={`${getPathPrefix()}/integrations`}
            className={styles['menu-sidebar-link']}
            underline="none"
          >
            <SidebarButton
              icon={
                <FontAwesomeIcon
                  className={styles['menu-sidebar-icon']}
                  icon={faPlug}
                />
              }
              text="Integrations"
              selected={currentPage === '/integrations'}
            />
          </Link>

          <Link
            href={`${getPathPrefix()}/data`}
            className={styles['menu-sidebar-link']}
            underline="none"
          >
            <SidebarButton
              icon={
                <FontAwesomeIcon
                  className={styles['menu-sidebar-icon']}
                  icon={faDatabase}
                />
              }
              text="Data"
              selected={currentPage === '/data'}
            />
          </Link>
        </Box>

        <Box sx={{ width: '100%' }}>
          <Divider sx={{ width: '100%', backgroundColor: 'white' }} />
          <Box sx={{ my: 2 }}>
            <Link href="mailto:support@aqueducthq.com" underline="none">
              <SidebarButton
                icon={
                  <FontAwesomeIcon
                    className={styles['menu-sidebar-icon']}
                    icon={faMessage}
                  />
                }
                text="Report Issue"
              />
            </Link>
          </Box>
        </Box>
      </Box>
    </>
  );

  return <Box className={styles['menu-sidebar']}>{sidebarContent}</Box>;
};

export default MenuSidebar;
