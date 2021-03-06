import socket
import sys
import time
import pickle
import whirlpool

import MySQLdb as mariadb

import sock_communication as sc

from uuid import uuid4

from  sql_errno import error

#подключение к mysql
mariadb_connection = mariadb.connect(user='dmelessa',
                                    password='ahegao',
                                    database='test3')
cursor = mariadb_connection.cursor()

#https://iximiuz.com/ru/posts/writing-python-web-server-part-2/#hybrid


def run_server(port=8000):
    serv_sock = create_serv_sock(port)
    cid = 0
    while True:
        client_sock = accept_client_conn(serv_sock, cid)
        serve_client(client_sock, cid)
        cid += 1


def serve_client(client_sock, cid):
    request = read_request(client_sock)
    if request is not None:
        response = handle_request(pickle.loads(request))
        write_response(client_sock, response, cid)
    else:
        print(f'Client #{cid} unexpectedly disconnected')


def create_serv_sock(serv_port):
    serv_sock = socket.socket(socket.AF_INET,
                              socket.SOCK_STREAM,
                              proto=0)
    serv_sock.bind(('', serv_port))
    serv_sock.listen()
    return serv_sock


def accept_client_conn(serv_sock, cid):
    client_sock, client_addr = serv_sock.accept()
    print(f'Client #{cid} connected {client_addr[0]}:{client_addr[1]}')
    return client_sock 


def read_request(client_sock, delimeter=b''):
    request = sc.recv_msg(client_sock)
    return request
    # try:
    #     while True:
    #         chunk = client_sock.recv(4)
    #         if not chunk:
    #             #клиент преждевременно отключился
    #             return None
            
    #         request += chunk
    #         if delimeter in request:
    #             request = request.rsplit(b'!', 1)[0]
    #             return request
    # except ConnectionResetError:
    #     #соединение было нежиданно разорванно
    #     return None
    # except:
    #     raise


def log_in(**kwargs):
    response = {}
    cursor.execute('''
        SELECT `users`.`id`
        ,      `users`.`login` as `login`
        ,      `users`.`group` as `group`
        ,      `user_passwd`.`user_passwd` as `password`
        ,      `user_passwd`.`auth_tok` as `token`
            FROM `users` INNER JOIN `user_passwd`
                ON `users`.`id` = `user_passwd`.`user_id`
                 WHERE `users`.`login` = %(login)s;
        ''', {'login': kwargs['login']
        })
    record = cursor.fetchall()

    response['status'] = 'fail'

    print(kwargs['password'])
    print(whirlpool.new(str.encode(kwargs['password'])).hexdigest())
    if record != ():
        print(record)
        record = record[0]
        if 'auth_token' in kwargs:
            if kwargs['auth_token'] == record[4]:
                response['status'] = 'success'
        elif record[3] == whirlpool.new(str.encode(kwargs['password'])).hexdigest():
            response['auth_token'] = str(uuid4())
            response['group'] = record[2]
            response['status'] = 'success'
            cursor.execute(f'''
                UPDATE `user_passwd`
                SET `auth_tok` = '{response['auth_token']}'
                WHERE user_id =  '{record[0]}';
                ''')
            mariadb_connection.commit()

    return response


def register(**kwargs):
    response = {}
    response['status'] ='fail'

    #проверка корректности введенных данных
    if 'login' not in kwargs or 'password' not in kwargs:
        return response
    if len(kwargs['login']) < 2 or len(kwargs['login']) > 20 or len(kwargs['password']) < 6:
        return response

    try:
        cursor.execute('''
            INSERT INTO `users`(`login`, `group`)
            SELECT '%(login)s', 'user';
        ''' % {'login': kwargs['login']
        })
    except Exception as e:
        print('Ошибка в добавлении нового пользователя')
        print('Логин: ', kwargs['login'])
        if e.args[0] == error['Duplicate_entry']:
            print("Пользователь с таким именем уже существует.")
            response['message'] = 'Пользователь с таким именем уже существует.'
        else:
            print(str(e))
        return response
    
    try:
        cursor.execute('''
            INSERT INTO `user_passwd`(`user_id`, `user_passwd`)
            SELECT id, '%(hash)s'
            FROM `users`
            WHERE login = '%(login)s';
        ''' % {'login': kwargs['login'],
               'hash': whirlpool.new(str.encode(kwargs['password'])).hexdigest()
        })
    except Exception as e:
        cursor.execute('''
        DELETE FROM `users`
        WHERE `login` = '%(login)s'
        ''' % {'login': kwargs['login']})
        mariadb_connection.commit()
        print('Ошибка при добавлении пароля нового пользователя')
        print('Логин: ', kwargs['login'])
        print(str(e))
        response['message'] = 'Ошибка при добавлении пароля нового пользователя'
        return response
    
    mariadb_connection.commit()
    response['status'] = 'success'
    return response
    

#insert information about game into sql
def add_game(**kwargs):
    '''game_name developer release rating description publishers platforms '''

    response = {}
    response['status'] = 'fail'

    cursor.execute('''
        INSERT IGNORE INTO `developers`(`developer_name`)
            SELECT
            '%(developer)s';
    ''' % {'developer': kwargs['developer']
    })

    cursor.execute('''
        INSERT IGNORE INTO `games`(`game_name`, `release_date`, `rating`, `description`)
            SELECT '%(name)s'
            ,'%(release)s'
            ,'%(rating)d'
            ,'%(description)s';
    ''' % {'name': kwargs['game_name'],
          'release': kwargs['release_date'],
          'rating': kwargs['rating'],
          'description': kwargs['description']
    })
    
    for genre in kwargs['genres']:
        cursor.execute('''
            INSERT IGNORE INTO `genres`(`genre_name`)
                SELECT
                '%(genre)s';
        ''' % {'genre': genre})
    
        cursor.execute('''
            INSERT INTO `game_genre`(`game_id`, `genre_id`)
            SELECT `game_id`, `genre_id` FROM `games`, `genres`
            WHERE `game_name` = '%(name)s'
            AND `genre_name` = '%(genre)s';
        ''' % {'name': kwargs['game_name'],
              'genre': genre})

    for publisher in kwargs['publishers']:
        cursor.execute('''
            INSERT IGNORE INTO `publishers`(`publisher_name`)
                SELECT
                '%(publisher)s';
        ''' % {'publisher': publisher})

        cursor.execute('''
            INSERT INTO `game_publisher`(`game_id`, `publisher_id`)
            SELECT `game_id`, `publisher_id` FROM `games`, `publishers`
            WHERE `game_name` = '%(name)s'
            AND `publisher_name` = '%(publisher)s';
        ''' % {'name': kwargs['game_name'],
              'publisher': publisher})


    cursor.execute('''
        INSERT INTO `game_developer`(`game_id`, `developer_id`)
        SELECT `game_id`, `developer_id` FROM `games`, `developers`
        WHERE `game_name` = '%(name)s'
        AND `developer_name` = '%(developer)s';
    ''' % {'name': kwargs['game_name'],
          'developer': kwargs['developer']})

    for platform in kwargs['platforms']:
        cursor.execute('''
            INSERT INTO `game_platform`(`game_id`, `platform_id`)
            SELECT `game_id`, `platform_id` FROM `games`, `platforms`
            WHERE `game_name` = '%(name)s'
            AND `platform_name` = '%(platform)s';
        ''' % {'name': kwargs['game_name'],
              'platform': platform})

    mariadb_connection.commit()
    response['status'] = 'success'
    return response
    # for image in kwargs['images']:
    #     cursor.execute('''
    #         INSERT INTO `pictures`(`game_id`, `source`)
    #     ''')
    ...


#поиск игр в базе данных по критериям 
def search(**kwargs):
    '''поиск игр в базе данных по критериям.
    Parameters:
        **kwargs: аргументы по ключу используются в качестве критериев.
    Возможно следующие ключи:
        `game_name`
        `genre_name`
        `developer_name`
        `year`
        `paltform_name`
    Retruns:
        dict: словарь с ключом `status`. Если `status` = 'success'
            то список игр с ключом `game_list`
    '''
    #default game_list
    response = {}
    query = '''
        SELECT DISTINCT `game_id`, `game_name`, YEAR(`release_date`), `rating`
        FROM `games`
        JOIN `game_genre` USING(`game_id`) JOIN `genres` USING(`genre_id`)
        JOIN `game_platform` USING(`game_id`) JOIN `platforms` USING(`platform_id`)
        JOIN `game_publisher` USING(`game_id`) JOIN `publishers` USING(`publisher_id`)
        JOIN `game_developer` USING(`game_id`) JOIN `developers` USING(`developer_id`)
    '''
    if 'game_name' in  kwargs and kwargs['game_name'] != '':
        query += '''WHERE game_name LIKE '%%%(game_name)s%%'
        ''' % {'game_name': kwargs['game_name']}
    else:
        query += '''WHERE game_name LIKE '%%%%' '''

    if 'genre_name' in  kwargs and kwargs['genre_name'] != '':
        query += ''' AND genre_name = '%(genre_name)s'
        ''' % {'genre_name': kwargs['genre_name']}

    if 'developer_name' in  kwargs and kwargs['developer_name'] != '':
        query += ''' AND developer_name='%(developer_name)s'
        ''' % {'developer_name': kwargs['developer_name']}

    if 'year' in  kwargs and kwargs['year'] != '':
        query += ''' AND YEAR(release_date)='%(year)s'
        ''' % {'year': kwargs['year']}

    if 'platform_name' in  kwargs and kwargs['platform_name'] != '':
        query += ''' AND platform_name='%(platform)s'
        ''' % {'platform': kwargs['platform_name']}
    if 'sort' in  kwargs and kwargs['sort'] != 'Сортировка':
        if kwargs['sort'] == 'По имени возр.':
            query += ''' ORDER BY `game_name` ASC;'''
        if kwargs['sort'] == 'По имени уб.':
            query += ''' ORDER BY `game_name` DESC;'''
        if kwargs['sort'] == 'По рейтингу возр.':
            query += ''' ORDER BY `rating` ASC;'''
        if kwargs['sort'] == 'По рейтингу уб.':
            query += ''' ORDER BY `rating` DESC;'''
    else:
        query += ''' ORDER BY `rating` DESC;'''

    #print(query)

    cursor.execute(query)
    result = cursor.fetchall()
    #for row in result:
    #   print(row)
    response['status'] = 'success'
    response['game_list'] = result
    return response

def change_password(**kwargs):
    '''login, old_password, new_password'''

    response = {}
    response['status'] = 'fail'
    if 'login' not in kwargs or 'old_password' not in kwargs or 'new_password' not in kwargs:
        return response
    query = '''
        SELECT `id`, `login`, `user_passwd`
        FROM `users` JOIN `user_passwd` ON `users`.`id` = `user_passwd`.`user_id`
        WHERE `users`.`login` = '%(login)s';
    ''' % {'login': kwargs['login']}

    cursor.execute(query)
    result = cursor.fetchall()
    print(result)
    if result != ():
        result = result[0]
        if result[2] != whirlpool.new(str.encode(kwargs['old_password'])).hexdigest():
            response['message'] = 'Wrong password'
            return response
        cursor.execute('''
        UPDATE `user_passwd`
        SET `user_passwd` = %s
        WHERE `user_id` = %s
        ''', (whirlpool.new(str.encode(kwargs['new_password'])).hexdigest(), result[0],))
        mariadb_connection.commit()
    else:
        response['message'] = 'User not found'
        return response
    response['status'] = 'success'
    return response


def get_game_info(**kwargs):
    response = {}
    game_id = kwargs['game_id']
    #get game_name release_date rating description
    query1 = '''
        SELECT game_name, release_date, rating, description
        FROM games
        WHERE game_id = '%(game_id)d'
    ''' % {'game_id': game_id}
    cursor.execute(query1)
    game_info = cursor.fetchall()
    response['game_name'] = game_info[0][0]
    response['release_date'] = game_info[0][1]
    response['game_score'] = game_info[0][2]
    response['description'] = game_info[0][3]
    #response['game_info'] = cursor.fetchall()

    #get_genres
    cursor.execute('''
        SELECT genre_name
        FROM genres
        JOIN game_genre using(genre_id)
        WHERE game_id = %(game_id)d
    ''' % {'game_id': game_id})
    response['genres'] = cursor.fetchall()

    #get_developer
    cursor.execute('''
        SELECT developer_name
        FROM developers
        JOIN game_developer USING(developer_id)
        WHERE game_id = '%(game_id)d'
    ''' % {'game_id': game_id})
    response['developer'] = cursor.fetchall()
    response['developer'] = response['developer'][0][0]

    #get_publisher
    cursor.execute('''
        SELECT publisher_name
        FROM publishers
        JOIN game_publisher USING(publisher_id)
        WHERE game_id = '%(game_id)d'
    ''' % {'game_id': game_id})
    response['publishers'] = cursor.fetchall()
    
    cursor.execute('''
        SELECT platform_name
        FROM platforms
        JOIN game_platform USING(platform_id)
        WHERE game_id = '%(game_id)d'
    ''' % {'game_id': game_id})
    response['platforms'] = cursor.fetchall()

    response['status'] = 'success'
    return response


def write_review(**kwargs):
    response = {}
    response['status'] = 'fail'

    if 'auth_token' not in kwargs or 'text' not in kwargs or 'score' not in kwargs:
        print('here')
        return response

    cursor.execute('''
        select id, login
        from users
        join user_passwd on users.id = user_passwd.user_id
        where auth_tok = '%(token)s'
    ''' % {'token': kwargs['auth_token']})
    login = cursor.fetchall()
    print(login)
    if login == ():
        print('her')
        return response
    
    query = '''
    insert INTO reviews(user_id, game_id, user_rating, text)
    select '%(user_id)d', '%(game_id)s', '%(user_rating)d', '%(text)s';
    ''' % {'user_id':  login[0][0],
            'game_id': kwargs['game_id'],
            'user_rating': kwargs['score'],
            'text': kwargs['text']}
    print(query)
    cursor.execute('''
    insert INTO reviews(user_id, game_id, user_rating, text)
    select '%(user_id)s', '%(game_id)s', '%(user_rating)d', '%(text)s';
    ''' % {'user_id': login[0][0],
            'game_id': kwargs['game_id'],
            'user_rating': kwargs['score'],
            'text': kwargs['text']})
    mariadb_connection.commit()
    response['status'] = 'success'

    return response


def get_reviews(**kwargs):
    response = {}
    response['status'] = 'fail'

    print(kwargs)

    if 'game_id' not in kwargs:
        return response

    cursor.execute("""
    SELECT login, user_rating, text
    FROM reviews
    JOIN users ON reviews.user_id = users.id
    JOIN games USING(game_id)
    WHERE game_id = %s
    """, (str(kwargs['game_id']),))
    response['reviews'] = cursor.fetchall()

    if response['reviews'] == ():
        return response
    response['status'] = 'success'    
    return response


Exec_request = {
    'login': log_in,
    'register': register,
    'add_game': add_game,
    'search': search,
    'get_game_info': get_game_info,
    'write_review': write_review,
    'get_reviews': get_reviews,
    'change_password': change_password
}


def handle_request(request):
    response = Exec_request.get(request['type'], lambda: 'Invalid')(**request)
    #Exec_request[request['type']](request)
   #time.sleep(5)
    return response


def write_response(client_sock, response, cid):
    #client_sock.sendall(pickle.dumps(response))
    sc.send_msg(client_sock, response)
    client_sock.close()
    print(f'Client #{cid} has been served')


if __name__ == '__main__':
    #args = {}
    #print(search())
    # add_game(game_name='The Last of Us',
    #           developer='Naughty Dog',
    #           release_date='2013-06-14',
    #           rating='95', 
    #           description='Twenty years after a pandemic radically transformed known civilization, infected humans run amuck and survivors kill one another for sustenance and weapons - literally whatever they can get their hands on. Joel, a salty survivor, is hired to smuggle a fourteen-year-old girl, Ellie, out of a rough military quarantine, but what begins as a simple job quickly turns into a brutal journey across the country',
    #           publishers=['SCEI'],
    #           platforms=['PS3'],
    #           genres=['action', 'rpg'])

    # add_game(game_name='Grand Theft Auto V',
    #           developer='Rockstar North',
    #           release_date='2014-11-18',
    #           rating='97', 
    #           description="Grand Theft Auto 5 melds storytelling and gameplay in unique ways as players repeatedly jump in and out of the lives of the game''s three protagonists, playing all sides of the game''s interwoven story.",
    #           publishers=['Rockstar Games'],
    #           platforms=['PS3', 'PC', 'XBOX one', 'PS4', 'PS3', 'XBOX 360'],
    #           genres=['action', 'adventure'])

    # add_game(game_name='Half-Life 2',
    #           developer='Valve Software',
    #           release_date='2004-11-16',
    #           rating='96', 
    #           description=" By taking the suspense, challenge and visceral charge of the original, and adding startling new realism and responsiveness, Half-Life 2 opens the door to a world where the player''s presence affects everything around him, from the physical environment to the behaviors -- even the emotions -- of both friends and enemies. The player again picks up the crowbar of research scientist Gordon Freeman, who finds himself on an alien-infested Earth being picked to the bone, its resources depleted, its populace dwindling. Freeman is thrust into the unenviable role of rescuing the world from the wrong he unleashed back at Black Mesa. And a lot of people -- people he cares about -- are counting on him.",
    #           publishers=['VU Games'],
    #           platforms=['PC'],
    #           genres=['action', 'shooter'])

    # register(login='admin',
    #           password='strong')
    # log_in(login='admin',
    #        password='strong')

    #print(whirlpool.new(str.encode('ahegao')).hexdigest())

    #search(year=2004, game_name='half', developer_name='Valve Software', platform_name='P')

    run_server(port=8000)