import requests
import datetime as dt
# import tweepy
# TO DO: import t_dict


def parse_truncated_link(link):
    from bs4 import BeautifulSoup
    if 'twitter.com/i' in link:
        try:
            soup = BeautifulSoup(requests.get(link).content, "html.parser")
            link = soup.find(attrs={"class": "tweet-text"})\
                    .find(attrs={"class": "twitter-timeline-link"})\
                    .text.rsplit()[0]
            if 'pic.twitter' in link:
                link = 'http://' + link
            link = requests.get(link).url
        except AttributeError:
            return link
    elif 'ln.is' in link:
        soup = BeautifulSoup(requests.get(link).content, "html.parser")
        link = soup.find("iframe")['src']
    return link.split("?")[0].split("#")[0]


class Facebook:

    'Interacts with Facebook Graph API'

    def __init__(self, token):
        from facebook import GraphAPI
        self._fb_token = token
        self._graph = GraphAPI(access_token=token, version='2.11')

    def get_page_info(self, page):
        api_data = self._graph.get_object(
            id=page,
            fields=
            'about,fan_count,picture.type(large),category,verification_status,link,name'
        )
        info = dict()
        available_info = list(api_data.keys())
        desired_info = ['about',
                        'category',
                        'fan_count',
                        'link',
                        'picture',
                        'name']
        for key in desired_info:
            if key in available_info:
                if key == 'picture':
                    info[key] = api_data['picture']['data']['url']
                else:
                    info[key] = api_data[key]
            else:
                info[key] = None

        info['page_id'] = page
        info['page_slug'] = info['link'].split('/')[3]

        if api_data['verification_status'] == 'blue_verified':
            info['verified'] = True
        else:
            info['verified'] = False
        return info

    def page_post_list(self, page, days_past=3):
        import datetime as dt
        fb_time_format = "%Y-%m-%dT%X"
        start = dt.datetime.utcnow() - dt.timedelta(days=days_past)
        api_data = self._graph.get_connections(page, "posts")
        post_list = []
        # TO DO: Implement async, yield, or return to requests
        while 'paging' in api_data:
            for post in api_data['data']:
                created = dt.datetime.strptime(
                    post['created_time'].split('+')[0],
                    fb_time_format
                )
                if created < start:
                    return post_list
                else:
                    post_list.append(post['id'])
            pagination = f'posts?after={api_data["paging"]["cursors"]["after"]}'
            api_data = self._graph.get_connections(page, pagination)
        return post_list

    def new_page_post_list(self, page):
        api_data = self._graph.get_connections(page, "posts")
        post_list = []
        # TO DO: Implement async, yield, or return to requests
        while 'paging' in api_data:
            for post in api_data['data']:
                post_list.append(post['id'])
            pagination = f'posts?after={api_data["paging"]["cursors"]["after"]}'
            api_data = self._graph.get_connections(page, pagination)
        return post_list

    def post_stats(self, post_id):
        emotions = ['like', 'wow', 'sad', 'haha', 'angry', 'love']
        emotion_params = \
                ['reactions.type({}).limit(0).summary(1).as({})'
                 .format(emotion.upper(), emotion)
                 for emotion in emotions]
        other_params = [
                'comments.summary(true).filter(toplevel){like_count,message}',
                'created_time', 'description', 'full_picture',
                'link', 'message', 'permalink_url', 'attachments',
                'properties', 'shares', 'source', 'type',
        ]
        fb_post_params = ','.join(emotion_params + other_params)
        api_data = self._graph.get_object(id=post_id, fields=fb_post_params)

        # Return False if any errors in the request ocurred
        if 'error' in api_data:
            return False
        elif 'permalink_url' not in api_data:
            return False

        # Creating the parsed response object:
        info = dict()

        # Parsing the reactions
        for emotion in emotions:
            if 'total_count' in api_data[emotion]['summary']:
                value = api_data[emotion]['summary']['total_count']
            else:
                value = 0
            info[emotion] = value

        # Main params (list can grow in the future)
        info['created_time'] = dt.datetime.strptime(
            api_data['created_time'], "%Y-%m-%dT%X%z")
        info['permalink_url'] = api_data['permalink_url']
        info['post_id'] = post_id
        info['page_id'] = post_id.split('_')[0]
        info['type'] = api_data['type']

        # Fields that don't appear in all posts
        info['shares'] = 0
        if 'shares' in api_data:
            info['shares'] = api_data['shares']['count']

        if 'attachments' in api_data and 'title' in api_data['attachments']['data'][0]:
            info['title'] = api_data['attachments']['data'][0]['title']
        else:
            info['title'] = None

        # Top comment -- NEW
        comms = comments_report(api_data)
        info['comments'] = comms['total_count']
        info['top_comment'] = comms['top_comment']
        info['message'] = api_data.get('message', None)
        info['link'] = api_data.get('link', None)
        info['full_picture'] = api_data.get('full_picture', None)

        engagement_fields = emotions + ['comments', 'shares']
        info['engagement'] = sum(info[key] for key in engagement_fields)

        return info


# Facebook helper functions
def comments_report(api_response):
    if api_response['comments']['data']:
        comm = api_response['comments']
        return dict(
            total_count=comm['summary']['total_count'],
            top_comment=comm['data'][0])
    else:
        return dict(
            total_count=0,
            top_comment=None)
