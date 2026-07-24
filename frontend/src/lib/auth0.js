import axios from "axios";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export const auth0LoginUrl = (returnTo) =>
  `${BACKEND}/api/auth0/login?returnTo=${encodeURIComponent(
    returnTo || window.location.origin
  )}`;

export const auth0LogoutUrl = () => `${BACKEND}/api/auth0/logout`;

export function loginWithAuth0(returnTo) {
  window.location.assign(auth0LoginUrl(returnTo));
}

export function logoutAuth0() {
  window.location.assign(auth0LogoutUrl());
}

export async function fetchAuth0Config() {
  try {
    const { data } = await axios.get(`${BACKEND}/api/auth0/config`);
    return data;
  } catch {
    return { enabled: false };
  }
}

export async function fetchAuth0Session() {
  try {
    const { data } = await axios.get(`${BACKEND}/api/auth0/me`, {
      withCredentials: true,
    });
    return data;
  } catch {
    return null;
  }
}
