import axios from 'axios';
import { API } from './api';

const authRequest = { withCredentials: true };

export async function followShow(showId) {
  const { data } = await axios.post(`${API}/shows/${showId}/follow`, {}, authRequest);
  return data;
}

export async function unfollowShow(showId) {
  const { data } = await axios.delete(`${API}/shows/${showId}/follow`, authRequest);
  return data;
}

export async function savePodcast(podcastId) {
  const { data } = await axios.post(`${API}/podcasts/${podcastId}/save`, {}, authRequest);
  return data;
}

export async function unsavePodcast(podcastId) {
  const { data } = await axios.delete(`${API}/podcasts/${podcastId}/save`, authRequest);
  return data;
}

export async function likePodcast(podcastId) {
  const { data } = await axios.post(`${API}/podcasts/${podcastId}/like`, {}, authRequest);
  return data;
}

export async function unlikePodcast(podcastId) {
  const { data } = await axios.delete(`${API}/podcasts/${podcastId}/like`, authRequest);
  return data;
}

export async function ratePodcast(podcastId, rating) {
  const { data } = await axios.put(`${API}/podcasts/${podcastId}/rating`, { rating }, authRequest);
  return data;
}

export async function clearPodcastRating(podcastId) {
  const { data } = await axios.delete(`${API}/podcasts/${podcastId}/rating`, authRequest);
  return data;
}

export async function hidePodcast(podcastId) {
  const { data } = await axios.post(`${API}/podcasts/${podcastId}/not-interested`, {}, authRequest);
  return data;
}

export async function restorePodcast(podcastId) {
  const { data } = await axios.delete(`${API}/podcasts/${podcastId}/not-interested`, authRequest);
  return data;
}

export { authRequest };
